"""The states a run ends in."""

#: Every state a run can end in. Anything else is still going.
TERMINAL_STATES = frozenset({"completed", "completed_with_orphans", "completed_unstructured", "failed", "abandoned"})
#: Ends that exit EXIT_RUN_FAILED. `abandoned` is one: the watching stopped, not the work.
FAILED_STATES = frozenset({"failed", "abandoned"})
