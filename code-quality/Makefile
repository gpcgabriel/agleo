# Running the quality gate (added by /quality-init) from the repository root, whose thresholds live in pyproject.toml /
# eslint.config.mjs / this folder, except for the shell tools, which take them only as flags below
.PHONY: check fast check-py check-ts check-sh check-dup

ROOT := $(shell git rev-parse --show-toplevel)
HERE := $(ROOT)/code-quality
FILES = git -C "$(ROOT)" ls-files --cached --others --exclude-standard
SH_FILES := $(shell $(FILES) '*.sh' 2>/dev/null)

check: check-py check-ts check-sh check-dup

fast:
	@cd "$(ROOT)" && ([ ! -f pyproject.toml ] || (uvx ruff check . && uvx ruff format --check . && uvx complexipy -q .))
	@cd "$(ROOT)" && ([ ! -f package.json ] || (npx eslint . && npx prettier --check .))
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

check-sh:
	@cd "$(ROOT)" && ([ -z "$(SH_FILES)" ] || (uvx --from shfmt-py shfmt -d -i 2 $(SH_FILES) \
	  && uvx --from shellcheck-py shellcheck $(SH_FILES)))

check-dup:
	@cd "$(ROOT)" && npx jscpd --config "$(HERE)/.jscpd.json" .
