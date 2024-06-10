# Django wrapper to database

This is a thin Django wrapper to the existing database.
Apart from the required Django `auth` models, etc., the main models are not "managed" by Django.
That is, the "truth" is the database itself, and any changes to the database structure must be effected both directly on the database, *and* in the Django models.


