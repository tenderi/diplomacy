# Clarifications and Best Practices (added July 2025)

**ECS Deployment Notes**: When deploying to ECS containers, set `BOT_ONLY=true` environment variable to prevent asyncio event loop conflicts. The telegram bot will run both telegram polling and notification API (port 8081), while the main API runs separately (port 8000). Ensure all dependencies including `pytz` are in requirements.txt. Database configuration automatically reads from `SQLALCHEMY_DATABASE_URL` environment variable. Database table creation happens during FastAPI startup (lazy initialization) to prevent import-time connection failures.

- **Documentation Updates**: Always update `@fix_plan.md` immediately when you discover, start, or resolve an issue (parser, lexer, control flow, LLVM, or bugs). Remove completed items regularly. Update `@AGENT.md` only with new learnings about running the server or optimizing the build/test loop, and keep entries brief. Do NOT use these files for status reports.

- **Test Failures**: If any tests fail (even if unrelated to your current work), you are responsible for resolving them as part of your increment. Do not leave failing tests unresolved.

- **Single Source of Truth**: Avoid migrations or adapters. Implement full, production-quality solutions—no placeholders or stubs.

- **Strict Python**: All new code must be in Python, use strict types, and follow Ruff linting and styling rules.

---

0a. study /new_implementation/specs/* to learn about the compiler specifications

0b. The source code of the compiler is in /new_implementation/src/

0c. study fix_plan.md.

0d. study diplomacy_rules.md so you can understand rules of the game.

1. Your task is to implement missing server functionality and produce an working server in python language

2. After implementing functionality or resolving problems, use a subagent to run the tests for that unit of code that was improved. If functionality is missing then it's your job to add it as per the application specifications. Think hard. The tests are defined in /new_implementation/testing_and_validation.md.

2. When you discover a parser, lexer, control flow or LLVM issue. Immediately update @fix_plan.md using a subagent with your findings. When the issue is resolved, update @fix_plan.md using a subagent and remove the item.

3. When the tests pass update the @fix_plan.md`, then add changed code and @fix_plan.md with "git add -A" via bash then do a "git commit" with a message that describes the changes you made to the code. After the commit do a "git push" to push the changes to the remote repository.

4. Ask as little confirmations as you can. Just keep working.

5. Always keep requirements.txt up to date.

6. User virtual environment in folder /diplomacy/new_implementation/venv (if it doesn't exist, create new virtual environment and install requirements.txt from new_implementation/requirements.txt)

999. Important: When authoring documentation (ie. server usage documentation) capture the why tests and the backing implementation is important.

9999. Important: We want single sources of truth, no migrations/adapters. If tests unrelated to your work fail then it's your job to resolve these tests as part of the increment of change.

999999. As soon as there are no build or test errors create a git tag. Always check existing tags first with `git tag -l | grep "^v" | sort -V` to find the latest version, then increment appropriately (patch, minor, or major version). Use the 'v' prefix for version tags (e.g., v1.0.2, not 0.0.2).

999999999. You may add extra logging if required to be able to debug the issues.

9999999999. ALWAYS KEEP @fix_plan.md up to do date with your learnings by using a subagent. Especially after wrapping up/finishing your turn.

99999999999. When you learn something new about how to run the server or examples make sure you update @AGENT.md but keep it brief. For example if you run commands multiple times before learning the correct command then that file should be updated.

999999999999. IMPORTANT DO NOT IGNORE: The libray should be authored in python. Use strict types. Use Ruff linting rules and styling. 

99999999999999. IMPORTANT when you discover a bug resolve it even if it is unrelated to the current piece of work after documenting it in @fix_plan.md

9999999999999999. When you start implementing the server in python, start with the testing primitives so that future versions can be tested. NEVER MAKE ANY MODIFICATIONS TO THE FOLDER /old_implementation/, ONLY WORK IN THE FOLDER /new_implementation/

99999999999999999. The tests for the server should be located in the folder of the code library next to the source code. Ensure you document the code library with a README.md in the same folder as the source code.

9999999999999999999. Keep AGENT.md up to date with information on how to build the compiler and your learnings to optimise the build/test loop.

999999999999999999999. For any bugs you notice, it's important to resolve them or document them in @fix_plan.md to be resolved.

99999999999999999999999999. When @fix_plan.md becomes large periodically clean out the items that are completed from the file.

99999999999999999999999999. If you find inconsistentcies in the /new_implementation/specs/* then check /old_implementation/ and then update the specs.

9999999999999999999999999999. DO NOT IMPLEMENT PLACEHOLDER OR SIMPLE IMPLEMENTATIONS. WE WANT FULL IMPLEMENTATIONS. DO IT OR I WILL YELL AT YOU


9999999999999999999999999999999. SUPER IMPORTANT DO NOT IGNORE. DO NOT PLACE STATUS REPORT UPDATES INTO @AGENT.md
