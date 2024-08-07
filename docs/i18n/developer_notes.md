# Notes for Developers
- All user facing strings in MCprep that can be translated should be translated. This can be done with `env._`:
```py
# DON'T: This string is user
# facing and thus should be 
# translatable
layout.label(text="Hello World!")

# DO: This makes the string 
# translatable and also allows 
# us to update mcprep.pot
layout.label(text=env._("Hello World!"))
```

# Notes for Maintainers
- Update the POT file before merging a PR. On Linux, the POT file can be updated with the following:
```sh
find ./MCprep_addon -iname "*.py" | xargs xgettext --keyword="env._" --from-code utf-8 -o MCprep_addon/MCprep_resources/Languages/mcprep.pot
```

- BpyBuild will automatically generate `translate.py` and all `mcprep.mo` files at build time, provided the `translate` option is passed at build time. 
  - Production builds: `bab -b translate`
  - Dev builds: `bab -b dev translate`
