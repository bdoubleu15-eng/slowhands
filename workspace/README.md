# Workspace

This directory is the agent's sandbox for file operations.

## Purpose

When the SlowHands agent creates, reads, or modifies files, it operates within this directory by default. This provides:

1. **Safety**: File operations are restricted to this directory
2. **Isolation**: Agent-created files don't affect the main codebase
3. **Visibility**: Easy to see what files the agent has created

## Usage

- Files created by the agent appear here
- The agent can read, write, and list files in this directory
- Clear this directory to start fresh

## Safety Note

The agent's `file_ops` tool is configured to only access files within this workspace. Attempting to access files outside this directory will be blocked.
