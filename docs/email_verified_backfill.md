# Email Verified Backfill

After we've [merged the email verification tracking PR](https://github.com/catalyst-cooperative/eel-hole/pull/135)
we'll need to update the email verification status of existing users.

Fortunately, you can export users from the Auth0 management dashboard:

1. manage.auth0.com -> User Management (sidebar) -> Users -> Import/Export Users (top right)
2. set the export format to CSV, and add these fields: `user_id -> auth0_id`, `email_verified -> email_verified`
3. wait patiently for the export to conclude, then download & `gunzip` it.

Then you can connect to Cloud SQL with `gcloud sql connect` and the credentials in Google Secret Manager.

Then, since you're updating the **production database**, you should grab a buddy to watch you do this so they can either stop you from doing something dumb or share in the blame if you wipe everything somehow.

Finally you can use the following SQL commands to update the database.

1. Create a staging table to temporarily hold the contents of the CSV:
   ```sql
   CREATE TEMP TABLE auth0_email_verified_import (
     auth0_id text PRIMARY KEY,
     email_verified boolean
   );
   ```
2. Use `\copy` to load the _local_ export into that table (remember to update path instead of blindly copy-pasting!):
   ```sql
   \copy auth0_email_verified_import(auth0_id, email_verified)
   FROM '/absolute/path/to/auth0-export.csv'
   WITH (FORMAT csv, HEADER true);
   ```
3. Are there enough rows? Compare against your local file.
   ```sql
   SELECT COUNT(*) FROM auth0_email_verified_import;
   ```
4. All of these users _should_ be in the database.
   ```sql
   SELECT COUNT(*)
   FROM "user" u
   JOIN auth0_email_verified_import i
     ON u.auth0_id = i.auth0_id;
   ```
5. If not... check to see who's not around - if they're early test users then we don't care:
   ```sql
   SELECT *
   FROM auth0_email_verified_import i
   LEFT OUTER JOIN "user" u
     ON u.auth0_id = i.auth0_id
   WHERE u.auth0_id IS NULL;
   ```
6. Take a look at what the change would look like:
   ```sql
   SELECT
     u.id,
     u.auth0_id,
     u.email,
     u.email_verified AS old_value,
     i.email_verified AS new_value
   FROM "user" u
   JOIN auth0_email_verified_import i
     ON u.auth0_id = i.auth0_id
   WHERE u.email_verified IS DISTINCT FROM i.email_verified
   LIMIT 50;
   ```
7. Count how many rows would be updated:
   ```sql
   SELECT COUNT(*)
   FROM "user" u
   JOIN auth0_email_verified_import i
     ON u.auth0_id = i.auth0_id
   WHERE u.email_verified IS DISTINCT FROM i.email_verified;
   ```
8. Actually run the update:
   ```sql
   UPDATE "user" u
   SET email_verified = i.email_verified
   FROM auth0_email_verified_import i
   WHERE u.auth0_id = i.auth0_id;
   ```
9. Check the final counts:
   ```sql
   SELECT email_verified, COUNT(*) FROM "user" GROUP BY email_verified;
   ```
   ```sql
   SELECT COUNT(*) FROM "user" WHERE email_verified IS FALSE;
   ```
