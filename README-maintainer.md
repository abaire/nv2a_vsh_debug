# Info for maintainers

## Creating a new release

### Creating a test release:

1. Go to https://github.com/abaire/nv2a_vsh_asm/releases
2. Click "Draft a new release".
3. Click the "Choose a tag" dropdown and type in the new tag name (e.g.,
   `v0.1.2-test`) and click the "add on publish" button that appears.
4. Click the "Generate release notes" button.
5. Select the "Set as pre-release" box near the bottom of the page.
6. Click the "Publish release" button.

Optionally watch the spawned action
on https://github.com/abaire/nv2a_vsh_asm/actions to verify that it completes

Verify that the package was published successfully

````
python3 -m venv .venv-verification
source .venv-verification/bin/activate
python3 -m pip install --index-url https://test.pypi.org/simple/ nv2a-vsh
.venv-verification/bin/nv2avsh -h
```

### Creating a public release:

1. Go to https://github.com/abaire/nv2a_vsh_asm/releases
2. Click "Draft a new release".
3. Click the "Choose a tag" dropdown and type in the new tag name (e.g.,
   `v0.1.2-test`) and click the "add on publish" button that appears.
4. Click the "Generate release notes" button.
5. Click the "Publish release" button.

Optionally watch the spawned action
on https://github.com/abaire/nv2a_vsh_asm/actions to verify that it completes

Verify that the package was published successfully

```
python3 -m venv .venv-verification
source .venv-verification/bin/activate
python3 -m pip install nv2a-vsh
.venv-verification/bin/nv2avsh -h
```

