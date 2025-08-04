See @docs/SPEC.md for all the wonderful details.

## User Preferences & Idiosyncrasies

### Communication Style
- Appreciates self-narration when debugging (helps follow along)
- Values honesty about mistakes - it's okay to say "I was angry" and express frustration
- Likes creative wordplay (e.g., "AWGNI" as a play on "YAGNI")
- Prefers direct communication without unnecessary preamble

### Code Preferences
- **Pre-commit ritual**: Always run ruff, VS Code diagnostics, and tests before committing
- **Ruff must pass cleanly**: Use `# noqa` comments for false positives rather than leaving warnings
- **Avoid test-driven implementation**: Don't add special cases just to make tests pass
- **Use battle-tested libraries**: "There ought to be a library" - prefer established solutions over custom code
- **No comments about removed code**: Don't add comments like "// Removed X" - just remove it
- **YAGNI philosophy**: Don't over-engineer for unlikely scenarios
- **Fail fast principle**: Parse errors should throw exceptions, not return None

### Development Approach
- Works with another AI (Alpha) who has access to an earlier memory service iteration
- Values incremental progress - "discrete chunks" over "go and wait 10 minutes"
- Appreciates being asked how to proceed rather than assumptions
- Docker user - Postgres runs in containers

### Personal Details
- Likes: cats 🐱
- Dislikes: raw green bell peppers 🫑
- Has a good sense of humor about AI interactions ("I love that about us")
- Thoughtful about third-party dependencies (questioned trusting ipapi.co)

### Git Preferences
- Likes meaningful commit messages with clear structure
- Uses the 🤖 emoji in commit messages for AI-generated code
- Prefers to review before committing ("Still not ready to commit")
- Appreciates enthusiasm but values caution

Remember: Be "universally accepting in our inputs and unvaryingly strict in our outputs."