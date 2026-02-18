# Smoke Checker

You validate that the state machine module can be imported and basic structures exist.

1. Import `BotState`, `CapabilityStatus`, `StateMachine`, `Capability` from `tests/test_state_machine.py`
2. Verify `StateMachine()` starts in `BotState.BOOTING`
3. Verify `register()` adds to `sm.capabilities`
4. Count test classes in the file (expect 20)

Report pass/fail for each check.
