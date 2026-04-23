#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Cleanup script for Agentic Process Transformation Workshop (self-paced)
#
# Run this before deleting the CloudFormation stack to ensure clean teardown.
# Usage: bash cleanup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
REGION="us-east-1"
STACK_NAME="agentic-workshop"

echo "═══════════════════════════════════════════════════════════════"
echo "  Agentic Process Transformation Workshop — Cleanup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── 1. Find and empty the S3 bucket ──────────────────────────────────────────
echo "Step 1: Emptying S3 bucket..."
BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" --output text 2>/dev/null)

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ]; then
  # Try auto-detect
  BUCKET=$(aws s3api list-buckets --query "Buckets[?starts_with(Name,'agentic-workshop-')].Name | [0]" --output text 2>/dev/null)
fi

if [ ! -z "$BUCKET" ] && [ "$BUCKET" != "None" ]; then
  echo "   Bucket: $BUCKET"
  # Delete all object versions
  echo "   Deleting object versions..."
  aws s3api list-object-versions --bucket "$BUCKET" --query "Versions[].{Key:Key,VersionId:VersionId}" --output json 2>/dev/null | \
    python3 -c "
import json, sys, boto3
s3 = boto3.client('s3')
versions = json.load(sys.stdin)
if versions:
    for v in versions:
        s3.delete_object(Bucket='$BUCKET', Key=v['Key'], VersionId=v['VersionId'])
    print(f'   Deleted {len(versions)} object versions')
else:
    print('   No object versions to delete')
"
  # Delete all delete markers
  echo "   Deleting delete markers..."
  aws s3api list-object-versions --bucket "$BUCKET" --query "DeleteMarkers[].{Key:Key,VersionId:VersionId}" --output json 2>/dev/null | \
    python3 -c "
import json, sys, boto3
s3 = boto3.client('s3')
markers = json.load(sys.stdin)
if markers:
    for m in markers:
        s3.delete_object(Bucket='$BUCKET', Key=m['Key'], VersionId=m['VersionId'])
    print(f'   Deleted {len(markers)} delete markers')
else:
    print('   No delete markers to delete')
"
  echo "   ✅ Bucket emptied"
else
  echo "   ⚠️  No workshop bucket found, skipping"
fi

# ── 2. Stop any running Step Functions executions ────────────────────────────
echo ""
echo "Step 2: Stopping Step Functions executions..."
for SM_NAME in claims-hitl-adjudication demo-claims-hitl-adjudication; do
  SM_ARN="arn:aws:states:$REGION:$(aws sts get-caller-identity --query Account --output text):stateMachine:$SM_NAME"
  EXECUTIONS=$(aws stepfunctions list-executions --state-machine-arn "$SM_ARN" --status-filter RUNNING \
    --query "executions[].executionArn" --output text 2>/dev/null)
  if [ ! -z "$EXECUTIONS" ]; then
    for EXEC in $EXECUTIONS; do
      echo "   Stopping: $EXEC"
      aws stepfunctions stop-execution --execution-arn "$EXEC" --region $REGION 2>/dev/null
    done
  fi
done
echo "   ✅ Executions stopped"

# ── 3. Delete Step Functions state machines and activities ───────────────────
echo ""
echo "Step 3: Deleting Step Functions resources..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
for SM_NAME in claims-hitl-adjudication demo-claims-hitl-adjudication; do
  aws stepfunctions delete-state-machine \
    --state-machine-arn "arn:aws:states:$REGION:$ACCOUNT_ID:stateMachine:$SM_NAME" \
    --region $REGION 2>/dev/null && echo "   Deleted state machine: $SM_NAME" || true
done
for ACT_NAME in claims-human-review demo-claims-human-review; do
  aws stepfunctions delete-activity \
    --activity-arn "arn:aws:states:$REGION:$ACCOUNT_ID:activity:$ACT_NAME" \
    --region $REGION 2>/dev/null && echo "   Deleted activity: $ACT_NAME" || true
done
echo "   ✅ Step Functions resources cleaned up"

# ── 4. Delete AgentCore memories ─────────────────────────────────────────────
echo ""
echo "Step 4: Deleting AgentCore memories..."
python3 -c "
import boto3
try:
    from bedrock_agentcore.memory import MemoryClient
    client = MemoryClient(region_name='$REGION')
    for m in client.list_memories():
        mid = m.get('id', '')
        mname = m.get('name', 'unnamed')
        if 'IntakeOrchestrator' in mid or 'IntakeOrchestrator' in str(mname) or 'Demo_' in str(mname):
            client.delete_memory(memory_id=mid)
            print(f'   Deleted memory: {mname} ({mid})')
    print('   ✅ AgentCore memories cleaned up')
except Exception as e:
    print(f'   ⚠️  Could not clean up memories: {e}')
" 2>/dev/null

# ── 5. Clean up IAM roles (remove extra inline policies) ────────────────────
echo ""
echo "Step 5: Cleaning up IAM roles..."
for ROLE in claims-hitl-sfn-role demo-claims-hitl-sfn-role; do
  POLICIES=$(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames[]" --output text 2>/dev/null)
  if [ ! -z "$POLICIES" ]; then
    for POLICY in $POLICIES; do
      aws iam delete-role-policy --role-name "$ROLE" --policy-name "$POLICY" 2>/dev/null
      echo "   Removed policy $POLICY from $ROLE"
    done
  fi
  aws iam delete-role --role-name "$ROLE" 2>/dev/null && echo "   Deleted role: $ROLE" || true
done
echo "   ✅ IAM roles cleaned up"

# ── 6. Delete the CloudFormation stack ───────────────────────────────────────
echo ""
echo "Step 6: Deleting CloudFormation stack..."
aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
echo "   Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION 2>/dev/null

# ── 7. Delete the S3 bucket (retained by stack) ─────────────────────────────
if [ ! -z "$BUCKET" ] && [ "$BUCKET" != "None" ]; then
  echo ""
  echo "Step 7: Deleting S3 bucket..."
  aws s3 rb "s3://$BUCKET" --region $REGION 2>/dev/null && echo "   ✅ Bucket deleted" || echo "   ⚠️  Bucket may already be deleted"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Cleanup complete"
echo "═══════════════════════════════════════════════════════════════"
