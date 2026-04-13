#!/usr/bin/env bash
# helpers.sh — shared utilities for 56_code_pipeline test scripts

# save_run_script <outfile> <spl_file> <adapter> [<key> <val> ...]
#
# Writes a self-contained bash script that runs the given spl3 workflow.
# Params whose values contain newlines or quotes are emitted as heredoc
# variables, so the script is safe to run directly without shell-quoting
# gymnastics — useful when code snippets are involved.
#
# Example generated output:
#   #!/usr/bin/env bash
#
#   CODE=$(cat <<'__SPL_PARAM_EOF__'
#   def binary_search(...):
#       ...
#   __SPL_PARAM_EOF__
#   )
#
#   spl3 run /path/to/02_review_code.spl \
#       --adapter ollama \
#       --param "code=$CODE" \
#       --param "lang=python" \
#       --param "model=llama3.2" \
#       --param "log_dir=/path/to/logs/good_code"
save_run_script() {
    local outfile="$1" spl_file="$2" adapter="$3"
    shift 3

    local -a keys=() vals=()
    while [ $# -ge 2 ]; do
        keys+=("$1")
        vals+=("$2")
        shift 2
    done

    mkdir -p "$(dirname "$outfile")"

    {
        echo "#!/usr/bin/env bash"
        echo ""

        # First pass: emit heredoc declarations for complex param values
        for i in "${!keys[@]}"; do
            local key="${keys[$i]}" val="${vals[$i]}"
            if [[ "$val" == *$'\n'* || "$val" == *'"'* || "$val" == *"'"* ]]; then
                local varname="${key^^}"
                echo "${varname}=\$(cat <<'__SPL_PARAM_EOF__'"
                printf '%s\n' "$val"
                echo "__SPL_PARAM_EOF__"
                echo ")"
                echo ""
            fi
        done

        # Second pass: spl3 run command
        local last=$(( ${#keys[@]} - 1 ))
        echo "spl3 run $spl_file \\"
        echo "    --adapter $adapter \\"
        for i in "${!keys[@]}"; do
            local key="${keys[$i]}" val="${vals[$i]}"
            local sep="\\"
            [ "$i" -eq "$last" ] && sep=""
            if [[ "$val" == *$'\n'* || "$val" == *'"'* || "$val" == *"'"* ]]; then
                local varname="${key^^}"
                echo "    --param \"${key}=\$${varname}\" $sep"
            else
                echo "    --param \"${key}=${val}\" $sep"
            fi
        done
    } > "$outfile"

    chmod +x "$outfile"
}
