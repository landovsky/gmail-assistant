# bin/common.sh — shared helpers for pipeline scripts
# Source this, don't execute it.

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Tools shared across all steps (never includes send_email or delete_email)
GMAIL_READ="mcp__gmail__search_emails mcp__gmail__read_email mcp__gmail__list_email_labels"
GMAIL_WRITE="mcp__gmail__modify_email mcp__gmail__batch_modify_emails"
GMAIL_DRAFT="mcp__gmail__draft_email"
LOCAL_TOOLS="Bash Read Glob Grep"

timestamp() { date "+%Y-%m-%d %H:%M:%S"; }

run_step() {
    local name="$1"
    local model="$2"
    local command="$3"
    local tools="$4"

    echo ""
    echo "=== [$( timestamp )] $name ==="

    claude --model "$model" \
        -p "/$command" \
        --allowedTools $tools

    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo "WARNING: $name exited with code $exit_code"
    fi
    return $exit_code
}
