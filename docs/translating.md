Guide to translate MCprep

# Translation Guidelines
To make sure translations are up to par with the standards we hold on the MCprep repo, all translators must follow these guidelines.
1. No AI for translations, such as Google Translate, ChatGPT, etc. AI translations are unreliable, differ massively in terms of quality between different languages, and don't take context properly into account. 
2. All translations must be confirmed by a regular user who knows the language in question. This is so we can verify that the translation is up to par.

Failure to follow these guidelines may prevent one from being able to contribute translations for MCprep in the future.

In addition, the following should be kept in mind:
- Not everything needs to be translated at once. If you're unsure of how to translate something, skip it.
- Translations should be close to the original strings in length. However, if this is not possible, then bring it up in a GitHub Issue.

# Understanding MCprep's Language format
MCprep uses PO files to store translations for files, which are compiled to MO files and stored in `MCprep_resources/Languages`. The layout of the `Languages`folder is the following:
```
Languages/
├── mcprep.pot
├── en_US/
│   └── LC_MESSAGES/
│       ├── mcprep.po
│       └── mcprep.mo
└── ...
```

Each language is stored in `i18n_code/LC_MESSAGES` (where `i18n_code` is the language code). All PO files are made from copying `mcprep.pot`, but `mcprep.pot` **should never be edited**. `mcprep.pot` is the template that all translations use.

# Making a Translation
This guide assumes you know the basics of `git` and forking in general.
1. Clone the MCprep repository
2. Create a folder with the language code of what you're translating for as the name, and in that folder, create a new folder called `LC_MESSAGES`. Using American English (`en_US`) as an example, it should look like this:
```
en_US/
└── LC_MESSAGES/
```

3. Next, copy `mcprep.pot` to `LC_MESSAGES` as `mcprep.po`. `mcprep.pot` itself **should never be modified**, only copied.
4. Start editing `mcprep.po`. If you're using a text editor, you'll see a bunch of strings like these:
```po
#: MCprep_addon/mcprep_ui.py:98
msgid "Restart blender"
msgstr ""

#: MCprep_addon/mcprep_ui.py:100
msgid "to complete update"
msgstr ""

#: MCprep_addon/mcprep_ui.py:121
msgid "Load mobs"
msgstr ""
```

Lines that begin with `msgid` are the original strings, those remain untouched. Lines that begin with `msgstr` contain the translations.

In general, we recommend using a PO editor such as [PoEdit](https://poedit.net). These editors make it easier to translate.

5. Compile the PO file to an MO file. There's several ways to do this:
  - Websites such as `https://po2mo.net`
  - Command line tools such as `msgfmt`
  - PO editors like PoEdit

Save the MO file as `mcprep.mo` in `LC_MESSAGES`, and your file structure should now look like this (using `en_US` as an example):
```
en_US/
└── LC_MESSAGES/
    ├── mcprep.po
    └── mcprep.mo
```

This conversion needs to be done each time the PO file is modified.

6. Build MCprep (see [CONTRIBUTING.md](https://github.com/Moo-Ack-Productions/MCprep/blob/dev/CONTRIBUTING.md) for steps on building MCprep) and test out the translation. *Note: MCprep follows the language set in Blender. If the language you're translating to is not supported in Blender, open a GitHub Issue*
7. Push the translations to your local fork of MCprep, open a PR, etc. Check [CONTRIBUTING.md](https://github.com/Moo-Ack-Productions/MCprep/blob/dev/CONTRIBUTING.md) for more details.
