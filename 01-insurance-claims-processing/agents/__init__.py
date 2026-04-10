# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Insurance Claims Processing — Shared Agent Modules
#
# Each module exposes a build_agent() factory function that returns a
# configured Strands Agent instance.  The factory pattern ensures each
# graph node gets a fresh agent (empty message history) per invocation,
# avoiding state bleed between pipeline runs.
