-- Replace <...> locally. Requires administrator privileges, not the BI role.
CREATE STORAGE INTEGRATION ECOMMERCE_S3
 TYPE=EXTERNAL_STAGE STORAGE_PROVIDER='S3' ENABLED=TRUE
 STORAGE_AWS_ROLE_ARN='<snowflake-read-role-arn>'
 STORAGE_ALLOWED_LOCATIONS=('s3://<bucket>/curated/');
DESC INTEGRATION ECOMMERCE_S3;
-- Use the returned IAM principal and external ID to configure AWS role trust.
-- Grant role only s3:GetObject for curated/* and constrained s3:ListBucket.
CREATE STAGE ECOMMERCE_CURATED URL='s3://<bucket>/curated/'
 STORAGE_INTEGRATION=ECOMMERCE_S3 FILE_FORMAT=(TYPE=PARQUET);
