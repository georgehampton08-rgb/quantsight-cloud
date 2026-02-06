# How to Find Your Cloud SQL Connection String

## Method 1: Using gcloud Command (Fastest)

Run these commands in your terminal:

```bash
# List your Cloud SQL instances
gcloud sql instances list

# Get connection details for your instance
gcloud sql instances describe YOUR_INSTANCE_NAME --format="value(connectionName)"
```

## Method 2: Google Cloud Console (Visual)

### Step 1: Go to Cloud SQL

1. Open <https://console.cloud.google.com/sql/instances>
2. You'll see a list of your SQL instances

### Step 2: Click on Your Instance

- Click on the instance name (probably something like `quantsight-sql` or similar)

### Step 3: Find Connection Info

In the instance details page, you'll see:

- **Connection name**: `PROJECT_ID:REGION:INSTANCE_NAME`
- **Public IP address** (if enabled)
- **Private IP address** (if using VPC)

### Step 4: Get Your Database Credentials

Go to the "Users" tab to see:

- **Username** (probably `postgres` or `quantsight_user`)
- **Password** (you set this when creating the instance)

### Step 5: Get Your Database Name

Go to the "Databases" tab to see:

- **Database name** (probably `quantsight`, `quantsight_db`, or `postgres`)

## Method 3: Check Your Local .env File

Your connection string might already be in your local `.env` file:

```bash
# Look in your backend directory
cat backend/.env
# or
cat .env
```

## Building the Connection String

Once you have the info, format it like this:

### For Cloud SQL Proxy (Recommended for Cloud Run)

```
postgresql://USERNAME:PASSWORD@/DATABASE_NAME?host=/cloudsql/CONNECTION_NAME
```

**Example:**

```
postgresql://postgres:mypassword@/quantsight_db?host=/cloudsql/quantsight-458498663186:us-central1:quantsight-sql
```

### For Direct Connection (if Public IP enabled)

```
postgresql://USERNAME:PASSWORD@PUBLIC_IP:5432/DATABASE_NAME
```

**Example:**

```
postgresql://postgres:mypassword@34.123.45.67:5432/quantsight_db
```

## What to Provide Me

Just copy-paste the full connection string in this format:

```
postgresql://username:password@...
```

I'll automatically set it as an environment variable on Cloud Run and redeploy.
