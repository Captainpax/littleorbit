"""Validated Unraid target lifecycle for the direct migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
import shlex
from uuid import uuid4


LIVE_ROOT = "/mnt/cache/little-orbit-live"
POSTGRES_ROOT = f"{LIVE_ROOT}/postgres"
ATTACHMENT_ROOT = f"{LIVE_ROOT}/attachments"
RELEASE_ROOT = f"{LIVE_ROOT}/releases"
STATE_PATH = f"{LIVE_ROOT}/.direct-migration-state"
PROJECT_LABEL = "com.docker.compose.project=little-orbit"


@dataclass(frozen=True)
class TargetGuard:
    """Unforgeable marker for cleanup of one proven-fresh target."""

    token: str

    @property
    def preparing_value(self) -> str:
        return f"preparing:{self.token}"

    @property
    def committed_value(self) -> str:
        return f"committed:{self.token}"

    @property
    def forward_cleaned_value(self) -> str:
        return f"forward-cleaned:{self.token}"

    @property
    def rollback_preparing_prefix(self) -> str:
        return f"rollback-preparing:{self.token}:"

    @property
    def rollback_committed_prefix(self) -> str:
        return f"rollback-committed:{self.token}:"


def new_guard() -> TargetGuard:
    """Create the run-specific capability before any target mutation."""

    return TargetGuard(uuid4().hex)


def _atomic_state_write(value: str) -> str:
    """Return a durable same-directory replace for one validated shell value."""

    state = shlex.quote(STATE_PATH)
    return (
        f"temporary={state}.new.$$; trap 'rm -f -- \"$temporary\"' EXIT; "
        f"umask 077; printf '%s\\n' {value} > \"$temporary\"; "
        "chown 0:0 \"$temporary\"; chmod 0600 \"$temporary\"; "
        "sync -f \"$temporary\"; "
        f"mv -T -- \"$temporary\" {state}; trap - EXIT; "
        f"sync -f {shlex.quote(LIVE_ROOT)}"
    )


def _remove_state(expected: str) -> str:
    state = shlex.quote(STATE_PATH)
    return (
        f"test \"$(cat -- {state})\" = {expected}; "
        f"rm -f -- {state}; sync -f {shlex.quote(LIVE_ROOT)}"
    )


def _fixed_root_guards() -> str:
    roots = (LIVE_ROOT, POSTGRES_ROOT, ATTACHMENT_ROOT, RELEASE_ROOT)
    checks = [
        "mountpoint -q /mnt/cache",
        "test \"$(findmnt -n -r -M /mnt/cache -o TARGET,FSTYPE)\" = '/mnt/cache btrfs'",
        "test \"$(findmnt -n -r -M /mnt/cache -o SOURCE)\" != ''",
        "case \"$(findmnt -n -r -M /mnt/cache -o SOURCE)\" in /dev/*) : ;; *) exit 78 ;; esac",
        "btrfs balance status /mnt/cache | grep -Fq 'No balance found'",
        "scrub_status=$(btrfs scrub status /mnt/cache 2>&1)",
        "! printf '%s\\n' \"$scrub_status\" | "
        "grep -Eiq 'status:[[:space:]]*(running|paused)'",
    ]
    for root in roots:
        quoted = shlex.quote(root)
        checks.extend((
            f"test -d {quoted}",
            f"test ! -L {quoted}",
            f"test \"$(readlink -f -- {quoted})\" = {quoted}",
        ))
    checks.extend((
        f"test \"$(stat -c %d -- {shlex.quote(LIVE_ROOT)})\" = "
        f"\"$(stat -c %d -- {shlex.quote(POSTGRES_ROOT)})\"",
        f"test \"$(stat -c %d -- {shlex.quote(LIVE_ROOT)})\" = "
        f"\"$(stat -c %d -- {shlex.quote(ATTACHMENT_ROOT)})\"",
        f"test \"$(stat -c %d -- {shlex.quote(LIVE_ROOT)})\" = "
        f"\"$(stat -c %d -- {shlex.quote(RELEASE_ROOT)})\"",
        f"test \"$(stat -c '%u:%g:%a' -- {shlex.quote(POSTGRES_ROOT)})\" = '999:70:700'",
        f"test \"$(stat -c '%u:%g' -- {shlex.quote(ATTACHMENT_ROOT)})\" = '65532:65532'",
        f"test \"$(stat -c '%u:%g' -- {shlex.quote(RELEASE_ROOT)})\" = '0:0'",
    ))
    return "; ".join(checks)


def begin_fresh_target(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Prove the exact target is unused, then create one cleanup marker."""

    empty_roots = (POSTGRES_ROOT, ATTACHMENT_ROOT, RELEASE_ROOT)
    checks = [_fixed_root_guards()]
    for root in empty_roots:
        quoted = shlex.quote(root)
        checks.append(
            f"test -z \"$(find {quoted} -mindepth 1 -maxdepth 1 -print -quit)\""
        )
    checks.extend((
        f"test -z \"$(docker ps -aq --filter label={shlex.quote(PROJECT_LABEL)})\"",
        "ids=$(docker ps -aq); if test -n \"$ids\"; then "
        "mounts=$(docker inspect --format '{{range .Mounts}}{{println .Source}}{{end}}' $ids); "
        f"! printf '%s\\n' \"$mounts\" | grep -Eq '^{LIVE_ROOT}(/|$)'; fi",
        f"test -z \"$(find {shlex.quote(LIVE_ROOT)} -mindepth 1 -maxdepth 1 -type d "
        "\\( -name '.attachments-migration-*' -o -name '.releases-migration-*' \\) "
        "-print -quit)\"",
        f"test ! -e {shlex.quote(STATE_PATH)}",
        f"test ! -L {shlex.quote(STATE_PATH)}",
        _atomic_state_write(shlex.quote(guard.preparing_value)),
        f"test \"$(stat -c '%F:%u:%g:%a:%h' -- {shlex.quote(STATE_PATH)})\" = "
        "'regular file:0:0:600:1'",
    ))
    run([*ssh, shell("; ".join(checks))])


def assert_only_postgres_running(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    run_stack: Callable[..., str], args: object,
) -> None:
    """Require only PostgreSQL and prove its exact host mount and PGDATA."""

    observed = run_stack(
        args, "unraid", "ps", "--services", "--status", "running", capture=True,
    )
    if observed.splitlines() != ["postgres"]:
        raise RuntimeError("only target PostgreSQL may run during direct migration")
    container = run_stack(args, "unraid", "ps", "-q", "postgres", capture=True)
    if not 12 <= len(container) <= 64 or "\n" in container or not all(
        character in "0123456789abcdef" for character in container.lower()
    ):
        raise RuntimeError("target PostgreSQL container identity is ambiguous")
    template = (
        '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}'
        "{{.Source}}|{{.RW}}{{println}}{{end}}{{end}}"
    )
    script = (
        f"value=$(docker inspect --format {shlex.quote(template)} {shlex.quote(container)}); "
        f"test \"$value\" = {shlex.quote(POSTGRES_ROOT + '|true')}"
    )
    run([*ssh, shell(script)])
    run_stack(
        args, "unraid", "exec", "-T", "postgres", "sh", "-ec",
        'test "$PGDATA" = /var/lib/postgresql/data/pgdata; '
        'test "$(readlink -f -- "$PGDATA")" = /var/lib/postgresql/data/pgdata',
    )


def assert_source_release_mount(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    run_stack: Callable[..., str], args: object,
) -> None:
    """Prove rollback reads the running API's exact immutable release bind."""

    container = run_stack(args, "unraid", "ps", "-q", "api", capture=True)
    if not 12 <= len(container) <= 64 or "\n" in container or not all(
        character in "0123456789abcdef" for character in container.lower()
    ):
        raise RuntimeError("source API container identity is ambiguous")
    template = (
        '{{range .Mounts}}{{if eq .Destination "/var/lib/little-orbit/releases"}}'
        "{{.Source}}|{{.RW}}{{println}}{{end}}{{end}}"
    )
    root = shlex.quote(RELEASE_ROOT)
    script = (
        f"value=$(docker inspect --format {shlex.quote(template)} {shlex.quote(container)}); "
        f"test \"$value\" = {shlex.quote(RELEASE_ROOT + '|false')}; "
        f"test -d {root}; test ! -L {root}; "
        f"test -n \"$(find {root} -type f -name '*.apk' -size +0c -print -quit)\""
    )
    run([*ssh, shell(script)])


def read_phase(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> str:
    """Read only this run's content-free target phase."""

    script = (
        f"test ! -L {shlex.quote(STATE_PATH)}; "
        f"if test ! -e {shlex.quote(STATE_PATH)}; then printf 'absent'; exit 0; fi; "
        f"test -f {shlex.quote(STATE_PATH)}; "
        f"cat -- {shlex.quote(STATE_PATH)}"
    )
    value = run([*ssh, shell(script)], capture=True)
    if value == "absent":
        return value
    if value not in {guard.preparing_value, guard.committed_value}:
        raise RuntimeError("target migration phase marker does not belong to this run")
    return value.split(":", maxsplit=1)[0]


def commit_script(guard: TargetGuard) -> str:
    """Return the final command appended to the same remote promotion."""

    state = shlex.quote(STATE_PATH)
    preparing = shlex.quote(guard.preparing_value)
    committed = shlex.quote(guard.committed_value)
    return (
        f"test \"$(cat -- {state})\" = {preparing}; "
        + _atomic_state_write(committed)
    )


def teardown_failed_target(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Erase the dedicated full target copy only while this run owns it."""

    run([*ssh, shell("; ".join(_teardown_commands(guard)))])


def _teardown_commands(guard: TargetGuard) -> list[str]:
    """Build the guarded teardown transaction for direct and recovery use."""

    expected = shlex.quote(guard.preparing_value)
    cleaned = shlex.quote(guard.forward_cleaned_value)
    return _teardown_commands_for_expected(expected, _atomic_state_write(cleaned))


def _teardown_commands_for_expected(expected: str, finish: str) -> list[str]:
    """Build teardown checks around a quoted literal or validated shell value."""

    roots = (POSTGRES_ROOT, ATTACHMENT_ROOT, RELEASE_ROOT)
    commands = [
        _fixed_root_guards(),
        f"test \"$(cat -- {shlex.quote(STATE_PATH)})\" = {expected}",
        f"ids=$(docker ps -aq --filter label={shlex.quote(PROJECT_LABEL)}); "
        "test -z \"$ids\" || docker rm -f $ids >/dev/null",
        f"test -z \"$(docker ps -aq --filter label={shlex.quote(PROJECT_LABEL)})\"",
    ]
    for root in roots:
        commands.append(
            f"find {shlex.quote(root)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +"
        )
    commands.extend((
        f"find {shlex.quote(LIVE_ROOT)} -mindepth 1 -maxdepth 1 -type d "
        "\\( -name '.attachments-migration-*' -o -name '.releases-migration-*' \\) "
        "-exec rm -rf -- {} +",
    ))
    commands.extend((
        f"chown 999:70 {shlex.quote(POSTGRES_ROOT)}; chmod 0700 {shlex.quote(POSTGRES_ROOT)}",
        f"chown 65532:65532 {shlex.quote(ATTACHMENT_ROOT)}; "
        f"chmod 0750 {shlex.quote(ATTACHMENT_ROOT)}",
        f"chown 0:0 {shlex.quote(RELEASE_ROOT)}; chmod 0755 {shlex.quote(RELEASE_ROOT)}",
        finish,
    ))
    return commands


def _state_preamble(pattern: str, *, allow_absent: bool) -> str:
    state = shlex.quote(STATE_PATH)
    absent = f"if test ! -e {state}; then printf 'absent'; exit 0; fi; "
    if not allow_absent:
        absent = f"test -e {state}; "
    return (
        f"test ! -L {state}; {absent}"
        f"test \"$(stat -c '%F:%u:%g:%a:%h' -- {state})\" = "
        "'regular file:0:0:600:1'; "
        f"value=$(cat -- {state}); printf '%s\\n' \"$value\" | grep -Eq {shlex.quote(pattern)}"
    )


def _forward_preamble(*, allow_absent: bool) -> str:
    return _state_preamble(
        "^(preparing:[0-9a-f]{32}|committed:[0-9a-f]{32}|"
        "forward-cleaned:[0-9a-f]{32})$",
        allow_absent=allow_absent,
    )


def recover_interrupted_forward(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
) -> tuple[str, str]:
    """Adopt a forward journal without erasing restart-required evidence."""

    finish = _atomic_state_write('"forward-cleaned:${value#*:}"')
    teardown = "; ".join(_teardown_commands_for_expected('"$value"', finish))
    script = (
        _forward_preamble(allow_absent=True) + "; phase=${value%%:*}; "
        "if test \"$phase\" = committed; then printf 'committed:preserved'; "
        "elif test \"$phase\" = forward-cleaned; then "
        "printf 'forward-cleaned:restart-required'; "
        f"elif test \"$phase\" = preparing; then {teardown}; "
        "printf 'forward-cleaned:restart-required'; else exit 78; fi"
    )
    value = run([*ssh, shell(script)], capture=True)
    outcomes = {
        "absent": ("absent", "not-needed"),
        "committed:preserved": ("committed", "preserved"),
        "forward-cleaned:restart-required": ("forward-cleaned", "restart-required"),
    }
    if value not in outcomes:
        raise RuntimeError("interrupted forward recovery returned an invalid outcome")
    return outcomes[value]


def complete_interrupted_forward(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
) -> None:
    """Remove only a valid cleaned journal after the exact source is healthy."""

    preamble = _state_preamble(
        "^forward-cleaned:[0-9a-f]{32}$", allow_absent=False,
    )
    run([*ssh, shell(preamble + "; " + _remove_state('"$value"'))])


def recover_failed_target(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> tuple[str, str, bool]:
    """Clean only this run's target and retain a restart-required journal."""

    preparing = shlex.quote(guard.preparing_value)
    committed = shlex.quote(guard.committed_value)
    cleaned = shlex.quote(guard.forward_cleaned_value)
    teardown = "; ".join(_teardown_commands(guard))
    script = (
        _forward_preamble(allow_absent=True) + "; "
        f"if test \"$value\" = {committed}; then printf 'committed:preserved'; "
        f"elif test \"$value\" = {cleaned}; then printf 'forward-cleaned:restart-required'; "
        f"elif test \"$value\" = {preparing}; then {teardown}; "
        "printf 'forward-cleaned:restart-required'; else exit 78; fi"
    )
    value = run([*ssh, shell(script)], capture=True)
    outcomes = {
        "absent": ("absent", "not-needed", True),
        "committed:preserved": ("committed", "preserved", False),
        "forward-cleaned:restart-required": (
            "forward-cleaned", "restart-required", True,
        ),
    }
    if value not in outcomes:
        raise RuntimeError("target recovery returned an invalid outcome")
    return outcomes[value]


def _rollback_preamble() -> str:
    pattern = (
        "^(committed:[0-9a-f]{32}|"
        "rollback-preparing:[0-9a-f]{32}:[0-9a-f]{32}|"
        "rollback-committed:[0-9a-f]{32}:[0-9a-f]{32})$"
    )
    return _state_preamble(pattern, allow_absent=False)


def begin_rollback(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Journal rollback intent before any local destination mutation."""

    preamble = _state_preamble("^committed:[0-9a-f]{32}$", allow_absent=False)
    value = f'"{guard.rollback_preparing_prefix}${{value#*:}}"'
    run([*ssh, shell(preamble + "; " + _atomic_state_write(value))])


def mark_rollback_committed(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Persist local promotion before leaving the source frozen."""

    pattern = f"^{guard.rollback_preparing_prefix}[0-9a-f]{{32}}$"
    preamble = _state_preamble(pattern, allow_absent=False)
    value = f'"{guard.rollback_committed_prefix}${{value##*:}}"'
    run([*ssh, shell(preamble + "; " + _atomic_state_write(value))])


def read_interrupted_rollback_phase(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
) -> str:
    """Read a validated rollback phase without returning either guard token."""

    script = _rollback_preamble() + "; printf '%s' \"${value%%:*}\""
    value = run([*ssh, shell(script)], capture=True)
    if value not in {"committed", "rollback-preparing", "rollback-committed"}:
        raise RuntimeError("interrupted rollback state is invalid")
    return value


def complete_interrupted_rollback(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
) -> None:
    """Restore forward committed state after rollback cleanup and source health."""

    pattern = "^rollback-preparing:[0-9a-f]{32}:[0-9a-f]{32}$"
    preamble = _state_preamble(pattern, allow_absent=False)
    run([*ssh, shell(
        preamble + "; " + _atomic_state_write('"committed:${value##*:}"'),
    )])


def complete_failed_forward(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Consume only this run's cleaned journal after source health proof."""

    expected = shlex.quote(guard.forward_cleaned_value)
    preamble = _state_preamble(
        f"^forward-cleaned:{guard.token}$", allow_absent=False,
    )
    run([*ssh, shell(preamble + "; " + _remove_state(expected))])


def recover_failed_rollback(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> tuple[str, str, bool]:
    """Classify only this rollback journal before local cleanup."""

    preparing = shlex.quote(guard.rollback_preparing_prefix)
    committed = shlex.quote(guard.rollback_committed_prefix)
    script = (
        _rollback_preamble() + "; "
        f"case \"$value\" in {preparing}*) printf 'rollback-preparing:cleanup-required' ;; "
        f"{committed}*) printf 'rollback-committed:preserved' ;; "
        "committed:*) printf 'committed:not-started' ;; *) exit 78 ;; esac"
    )
    value = run([*ssh, shell(script)], capture=True)
    outcomes = {
        "rollback-preparing:cleanup-required": (
            "rollback-preparing", "cleanup-required", True,
        ),
        "rollback-committed:preserved": (
            "rollback-committed", "preserved", False,
        ),
        "committed:not-started": ("committed", "not-started", False),
    }
    if value not in outcomes:
        raise RuntimeError("rollback recovery returned an invalid outcome")
    return outcomes[value]


def complete_failed_rollback(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
    guard: TargetGuard,
) -> None:
    """Restore committed state only for this recovered rollback."""

    pattern = f"^{guard.rollback_preparing_prefix}[0-9a-f]{{32}}$"
    preamble = _state_preamble(pattern, allow_absent=False)
    run([*ssh, shell(
        preamble + "; " + _atomic_state_write('"committed:${value##*:}"'),
    )])


def recovery_record(*, phase: str, target: str, source: str) -> dict[str, str]:
    """Return stable, content-free failure evidence."""

    return {"target_phase": phase, "target_cleanup": target, "source_writers": source}


def encode_recovery(record: dict[str, str]) -> str:
    """Serialize recovery evidence without content or exception arguments."""

    return json.dumps(record, sort_keys=True, separators=(",", ":"))
