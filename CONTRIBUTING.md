# Contributing

Start with the offline demo and `docs/IMPLEMENTATION_STATUS.md`. Preserve the declared grains, exact money arithmetic, stable fact attribution and atomic ledger/watermark boundary.

Before opening a pull request:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q pipeline jobs lambdas scripts orchestration
```

Add behavioral tests when changing business rules or failure handling. Cloud changes need account integration evidence; a syntax check is not a successful cloud run. Document version selection and reproduction commands. Do not commit secrets, source exports, Terraform state, real customer records, screenshots containing account details, or raw voice recordings. Use only synthetic fixtures.

The public tutorial text lives in `tutorial/`. Private planning and raw production assets are ignored. Update README/status evidence when implemented behavior differs from the target architecture.
