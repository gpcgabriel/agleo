# Running the quality gate (added by /quality-init) from the repository root, whose thresholds live in pyproject.toml /
# eslint.config.mjs / this folder, except for the C/C++ and shell tools, which take them only as flags below
.PHONY: check fast check-py check-ts check-c check-sh check-dup

ROOT := $(shell git rev-parse --show-toplevel)
HERE := $(ROOT)/code-quality
FILES = git -C "$(ROOT)" ls-files --cached --others --exclude-standard
C_SOURCES := $(shell $(FILES) '*.c' '*.cc' '*.cpp' 2>/dev/null)
C_HEADERS := $(shell $(FILES) '*.h' '*.hpp' 2>/dev/null)
SH_FILES := $(shell $(FILES) '*.sh' 2>/dev/null)

check: check-py check-ts check-c check-sh check-dup

fast:
	@cd "$(ROOT)" && ([ ! -f pyproject.toml ] || (uvx ruff check . && uvx ruff format --check . && uvx complexipy -q .))
	@cd "$(ROOT)" && ([ ! -f package.json ] || (npx eslint . && npx prettier --check .))
	@cd "$(ROOT)" && ([ -z "$(C_SOURCES)" ] || (uvx clang-format --style=file --fallback-style=Google --dry-run --Werror \
	  $(C_SOURCES) $(C_HEADERS) && uvx lizard -C 15 -w $(C_SOURCES)))
	@cd "$(ROOT)" && ([ -z "$(SH_FILES)" ] || (uvx --from shfmt-py shfmt -d -i 2 $(SH_FILES) \
	  && uvx --from shellcheck-py shellcheck $(SH_FILES)))

check-py:
	@cd "$(ROOT)" && ([ ! -f pyproject.toml ] || (uvx ruff check . && uvx ruff format --check . \
	  && uvx complexipy -q . \
	  && uv run pyright && uv run pytest && uv run vulture \
	  && uv export --format requirements-txt --no-hashes -q | uvx pip-audit --no-deps --disable-pip -r /dev/stdin))

check-ts:
	@cd "$(ROOT)" && ([ ! -f package.json ] || (npx tsc --noEmit && npx eslint . && npx prettier --check . \
	  && npx vitest run --coverage && npx knip \
	  && npx madge --circular --extensions ts,tsx --exclude 'node_modules|\.next|dist' . \
	  && npm audit --audit-level=high))

check-c:
	@cd "$(ROOT)" && ([ -z "$(C_SOURCES)" ] || (uvx clang-format --style=file --fallback-style=Google --dry-run --Werror \
	  $(C_SOURCES) $(C_HEADERS) && uvx lizard -C 15 -w $(C_SOURCES) \
	  && uvx cppcheck --quiet --error-exitcode=1 --enable=warning,style,performance,portability $(C_SOURCES) \
	  && cmake -S "$(HERE)" -B build/quality -DCMAKE_BUILD_TYPE=Debug && cmake --build build/quality \
	  && uvx clang-tidy -p build/quality --quiet --warnings-as-errors='*' \
	     --checks='clang-analyzer-*,bugprone-*,performance-*' $(C_SOURCES) \
	  && ctest --test-dir build/quality --output-on-failure \
	  && uvx gcovr --root . --exclude 'build/' --exclude '.*/test_[^/]*$$' --fail-under-line 80 build/quality))

check-sh:
	@cd "$(ROOT)" && ([ -z "$(SH_FILES)" ] || (uvx --from shfmt-py shfmt -d -i 2 $(SH_FILES) \
	  && uvx --from shellcheck-py shellcheck $(SH_FILES)))

check-dup:
	@cd "$(ROOT)" && npx jscpd --config "$(HERE)/.jscpd.json" .
