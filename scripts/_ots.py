"""Minimal OpenTimestamps client built directly on the `opentimestamps`
library's calendar/timestamp primitives, bypassing the `opentimestamps-client`
(`ots`) CLI entirely.

Why not just shell out to `ots stamp` / `ots upgrade`, the way other scripts
in this repo shell out to `git`: on this machine (Windows), the `ots` CLI is
broken out of the box. `otsclient.cmds` unconditionally imports `bitcoin.rpc`,
which imports `bitcoin.core.key`, which calls
`ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl'))` -
`ctypes.util.find_library` essentially never resolves standard library names
on Windows, so that import crashes before any command (stamp, upgrade,
verify) ever runs, regardless of whether Bitcoin RPC is actually needed for
that particular command. Confirmed live: `uv run ots --help` raises
`TypeError: argument of type 'NoneType' is not iterable` deep inside
bitcoin/core/key.py - not a hypothetical compatibility note, an observed one.

The underlying `opentimestamps` package (the actual proof format + calendar
HTTP client) has no such dependency - `opentimestamps.calendar.RemoteCalendar`
is pure `urllib` plus the proof format's own (de)serialization code. This
module uses that directly: submit the file's SHA-256 digest to a small set of
public calendar servers, merge their responses into one Timestamp, and
serialize using the exact on-disk `.ots` format (`DetachedTimestampFile`,
from `opentimestamps.core.timestamp` - the same class `ots stamp` itself
would use to write the file).

Because the digest is submitted directly (no intermediate reduction ops), the
resulting Timestamp's top-level message is always the file digest itself, so
upgrading later is a flat merge, not a tree walk: re-query each calendar for
that same digest and merge whatever it now returns (still a bare
`PendingAttestation`, or - once the block that includes this digest has been
mined and the calendar has propagated that - a real
`BitcoinBlockHeaderAttestation` with the block height) into the existing
Timestamp.

Known limitation, stated plainly rather than implied away: `is_confirmed()`
here means "a calendar server told us which Bitcoin block height includes
this digest." It does not independently reconstruct that block's merkle root
from a Bitcoin node or block explorer to confirm the calendar isn't lying
about the height - that would need an extra network call this module doesn't
make. Same trust boundary the `ots` CLI's calendar communication would also
have; worth closing in a later pass (e.g. a block-explorer cross-check in
verify), not pretended to be closed now.
"""
import hashlib
from pathlib import Path

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import BytesDeserializationContext, BytesSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

# The same public calendar servers the `ots` CLI uses by default.
DEFAULT_CALENDAR_URLS = [
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]

CALENDAR_TIMEOUT = 15


def sha256_file(path: Path) -> bytes:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.digest()


def stamp_digest(digest: bytes, calendar_urls: list[str] = DEFAULT_CALENDAR_URLS) -> Timestamp:
    """Submit `digest` to each calendar server, merge their responses into
    one Timestamp. Raises RuntimeError only if every calendar fails - a
    minority of unreachable calendars is fine, same tolerance `ots stamp`
    itself has."""
    merged = Timestamp(digest)
    successes = []
    errors = []
    for url in calendar_urls:
        try:
            result = RemoteCalendar(url).submit(digest, timeout=CALENDAR_TIMEOUT)
            merged.merge(result)
            successes.append(url)
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    if not successes:
        raise RuntimeError(
            "Every calendar server rejected the stamp request:\n" + "\n".join(errors)
        )

    return merged


def serialize_ots(digest: bytes, timestamp: Timestamp) -> bytes:
    detached = DetachedTimestampFile(OpSHA256(), timestamp)
    ctx = BytesSerializationContext()
    detached.serialize(ctx)
    return ctx.getbytes()


def deserialize_ots(data: bytes) -> DetachedTimestampFile:
    ctx = BytesDeserializationContext(data)
    return DetachedTimestampFile.deserialize(ctx)


def pending_calendar_urls(timestamp: Timestamp) -> set[str]:
    return {
        attestation.uri
        for _msg, attestation in timestamp.all_attestations()
        if isinstance(attestation, PendingAttestation)
    }


def is_confirmed(timestamp: Timestamp) -> bool:
    return any(
        isinstance(attestation, BitcoinBlockHeaderAttestation)
        for _msg, attestation in timestamp.all_attestations()
    )


def confirmed_heights(timestamp: Timestamp) -> list[int]:
    return [
        attestation.height
        for _msg, attestation in timestamp.all_attestations()
        if isinstance(attestation, BitcoinBlockHeaderAttestation)
    ]


def upgrade(timestamp: Timestamp, digest: bytes) -> bool:
    """Re-query every calendar this Timestamp still has a pending attestation
    for, merging in whatever each one now returns. Returns True if the
    serialized proof changed (i.e. at least one calendar returned something
    beyond what was already recorded)."""
    before = serialize_ots(digest, timestamp)
    for url in pending_calendar_urls(timestamp):
        try:
            result = RemoteCalendar(url).get_timestamp(digest, timeout=CALENDAR_TIMEOUT)
            timestamp.merge(result)
        except Exception:
            continue  # still pending at this calendar, or it's unreachable right now
    after = serialize_ots(digest, timestamp)
    return before != after
