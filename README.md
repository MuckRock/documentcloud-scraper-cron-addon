
# DocumentCloud Cron Add-On Example

This repository contains an example Cron Add-On for DocumentCloud.  It is
designed to be forked and modified to allow one to easily write Add-Ons to
bring custom functionality to DocumentCloud.

## Files

### addon.py

This file is part of the `python-documentcloud` library.

This file contains a base class `CronAddOn`, which implements shared
functionality for all DocumentCloud Cron Add-Ons to use.  In most cases, you
should not need to edit this file.  You will subclass this class in `main.py`.

Upon initializing this class, it reads the environment variables `DC_USERNAME`
and `DC_PASSWORD` which must be set as GitHub secrets.  It then creates a
`client` for you to access the DocumentCloud API.

* `client` - A DocumentCloud client.  This is a python library
  (https://github.com/MuckRock/python-documentcloud) allowing easy access to
  the DocumentCloud API.  It will be configured with the access token passed
  in, which gives you access to the API as the user who activated the Add-On
  for 5 minutes. (NOTE: we may need a way to pass in a refresh token if Add-Ons
  need to run for more than 5 minutes)

There are also some methods which provide useful functionality for an Add-On.

* `send_mail(self, subject, content)` - This is used to email yourself at the
  email address associated with your DocumentCloud account.  This can be used
  to send a notification when an Add-On run is complete or just to send
  additional information to the user who ran the Add-On.  It takes two
  character strings, one for the subject and one for the body content of the
  email.  The content is plain text and does not currently support Markdown or
  HTML.

### main.py

This is the file to edit to implement your Cron Add-On specific functionality.
You should define a class which inherits from `CronAddOn` from `addon.py`.
Then you can instantiate a new instance and call the main method, which is the
entry point for your Add-On logic.  You may access the data parsed by `AddOn`
as well as using the helper methods defined there.  The `Alert` example
Add-On demonstrates using many of these features.

If you need to add more files, remember to instantiate the main Add-On class
from a file called `main.py` - that is what the GitHub action will call on the
cron schedule.

### requirements.txt

This is a standard `pip` `requirements.txt` file.  It allows you to specify
python packages to be installed before running the Add-On.  You may add any
dependencies your Add-On has here.  By default we install the
`python-documentcloud` API library and the `requests` HTTP request package.

### .github/workflows/addons.yml

This is the GitHub Actions configuration file for running the add-on.  It
references a reusable workflow from the
`MuckRock/documentcloud-addon-workflows` repository.  This workflow sets up
python, installs dependencies and runs the `main.py` to start the Add-On. It
accepts two inputs:
* `timeout` - Number of minutes to time out.  The default is `5`.  You may
  increase this if your add-on will run for longer than that.
* `python-version` - The version of python you would like to use.  Defaults to `3.10`.

To set an input:
```yaml
jobs:
  Run-Add-On:
    uses: MuckRock/documentcloud-addon-workflows/.github/workflows/update-config.yml@v1
    with:
      timeout: 30
```

It is recommended you use the reusable workflow in order to receive future
improvements to the workflow.  If needed you may fork the reusable workflow and
edit it as needed. If you do edit it, you should leave the first step in place,
which uses the UUID as its name, to allow DocumentCloud to identify the run.

It would be possible to make a similar workflow for other programming languages
if one wanted to write Cron Add-Ons in a language besides Python.
