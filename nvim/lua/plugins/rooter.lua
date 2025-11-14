return {
  'notjedi/nvim-rooter.lua',
  opts = {
    rooter_patterns = { '.git', '.pylintrc', 'pyproject.toml' },  -- optional
    manual = false,  -- auto-change cwd
  },
  lazy = false,  -- load on startup
}
