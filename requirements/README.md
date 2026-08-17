# Dependency contract

`faue-core` owns what every service depends on. Services declare their **role**
and never pin a shared library themselves.

| File | Used by |
|---|---|
| `base.in` | everything |
| `web.in` | HTTP-serving services |
| `worker.in` | background workers |
| `ml.in` | **ase only** — must never enter the gateway image |
| `dev.in` | local development and CI |
| `constraints.txt` | shared pins; every role resolves against it |

```bash
pip-compile --constraint requirements/constraints.txt requirements/base.in
pip-compile --constraint requirements/constraints.txt requirements/web.in
# ... one per role
```

Adding a dependency: put it in the `.in` file for the **narrowest** role that
needs it, then recompile. If two services need different versions of the same
library, that is a design signal — fix the constraint, not the service.
