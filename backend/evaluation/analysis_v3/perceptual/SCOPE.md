# Scope boundary

This branch is evaluation-only for #455.

It must not:
- modify `backend/config/capabilities.json`;
- register a production engine;
- persist perceptual evidence;
- change Inspector/Breakdown/Ask behavior;
- add semantic labels derived from low-level descriptors;
- add a production dependency.

Promotion decisions belong to #459 only after #455 and #457 gates are satisfied.
