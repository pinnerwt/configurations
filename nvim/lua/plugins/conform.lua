return {
  "stevearc/conform.nvim",
  opts = {
    -- LazyVim will use these options when formatting with the conform.nvim formatter
    default_format = {
      timeout_ms = 3000,
      async = false, -- not recommended to change
      quiet = false, -- not recommended to change
    },
    formatters_by_ft = {
      lua = { "stylua" },
      sh = { "shfmt" },
      -- python = { "yapf" },
      python = { "ruff_fix", "ruff_format", "ruff_organize_imports" },
      json = { "jq" },
    },
    -- The options you set here will be merged with the builtin formatters.
    -- You can also define any custom formatters here.
    formatters = {
        jq = {
                args = { "--indent", "4" }
            },
      injected = { options = { ignore_errors = true } },
    },
  },
}
