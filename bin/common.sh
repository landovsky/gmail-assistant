# bin/common.sh — shared helpers for pipeline scripts
# Source this, don't execute it.

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Tools shared across all steps (never includes send_email or delete_email)
GMAIL_READ="mcp__gmail__search_emails mcp__gmail__read_email mcp__gmail__list_email_labels"
GMAIL_WRITE="mcp__gmail__modify_email mcp__gmail__batch_modify_emails"
GMAIL_DRAFT="mcp__gmail__draft_email"
LOCAL_TOOLS="Bash Read Glob Grep"

# --- Logging ---
# GMA_LOG_LEVEL: debug | info (default) | warn | error
GMA_LOG_LEVEL="${GMA_LOG_LEVEL:-info}"

_log_level_num() {
    case "$1" in
        debug) echo 0 ;; info) echo 1 ;; warn) echo 2 ;; error) echo 3 ;; *) echo 1 ;;
    esac
}

_log() {
    local level="$1"; shift
    local threshold
    threshold=$(_log_level_num "$GMA_LOG_LEVEL")
    local current
    current=$(_log_level_num "$level")
    [[ $current -lt $threshold ]] && return

    local tag
    tag=$(printf "%-5s" "$level" | tr '[:lower:]' '[:upper:]')
    echo "[$( date "+%Y-%m-%d %H:%M:%S" )] ${tag} $*"
}

log_debug() { _log debug "$@"; }
log_info()  { _log info  "$@"; }
log_warn()  { _log warn  "$@"; }
log_error() { _log error "$@"; }

# --- Step runner ---
run_step() {
    local name="$1"
    local model="$2"
    local command="$3"
    local tools="$4"

    log_info "--- $name: starting (model=$model, command=/$command) ---"
    log_debug "$name: allowedTools=$tools"

    local start_ts
    start_ts=$(date +%s)

    claude --model "$model" \
        -p "/$command" \
        --allowedTools $tools

    local exit_code=$?
    local end_ts
    end_ts=$(date +%s)
    local duration=$(( end_ts - start_ts ))

    if [[ $exit_code -eq 0 ]]; then
        log_info "--- $name: finished (${duration}s) ---"
    else
        log_error "--- $name: failed with exit code $exit_code (${duration}s) ---"
    fi
    return $exit_code
}
