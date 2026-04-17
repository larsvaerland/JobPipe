# Security

## Scope

This repository must not contain live secrets, personal candidate data, inbox exports, tokens, or local runtime state.

## Rules

- Never commit API keys, OAuth credentials, tokens, cookies, or passwords.
- Never commit personal application history, inbox-derived data, or private candidate documents.
- Use placeholder values only in examples.
- Keep real local configuration in ignored files or external secret stores.
- Treat generated local state as disposable and non-versioned.

## If Something Sensitive Was Committed

Assume it is exposed.

1. remove it from the repository
2. rotate the credential or invalidate the token
3. clean affected history if needed
4. check examples and docs for accidental copies

## Practical Default

- examples are allowed
- placeholders are allowed
- live secrets are not
