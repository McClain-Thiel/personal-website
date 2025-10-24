#!/usr/bin/env bash

# macOS space reclamation script focused on “System Data” culprits.
# It cleans Xcode build data and simulators, prunes Docker (aggressive optional),
# and thins/deletes local Time Machine snapshots. Includes optional cache pruning.
#
# Usage: bash cleanup_mac_space.sh
#
# Notes:
# - Close Xcode and Docker Desktop before running for best results.
# - Time Machine snapshot deletion requires admin (will prompt for password).
# - This script is interactive and asks before any destructive action.

set -e

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "[info] %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[31m[error]\033[0m %s\n" "$*"; }

confirm() {
  local prompt="$1"; shift || true
  read -r -p "$prompt [y/N]: " resp
  case "$resp" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

exists() { command -v "$1" >/dev/null 2>&1; }

human_df_root() {
  df -h / | awk 'NR==1 || NR==2 {print}'
}

print_sizes() {
  bold "-- Disk Free --"; human_df_root; echo
  bold "-- Xcode --"
  du -sh "$HOME/Library/Developer/Xcode/DerivedData" 2>/dev/null || true
  du -sh "$HOME/Library/Developer/Xcode/Archives" 2>/dev/null || true
  du -sh "$HOME/Library/Developer/Xcode/iOS DeviceSupport" 2>/dev/null || true
  du -sh "$HOME/Library/Developer/CoreSimulator/Devices" 2>/dev/null || true
  echo
  bold "-- Docker --"
  if exists docker; then
    docker system df || true
  else
    info "docker not installed or not in PATH"
  fi
  echo
  bold "-- Time Machine Local Snapshots --"
  if exists tmutil; then
    tmutil listlocalsnapshots / || true
  else
    info "tmutil not available"
  fi
  echo
}

bold "macOS Space Cleanup"
info "Close Xcode and Docker Desktop before proceeding."
echo

bold "===== BEFORE ====="
print_sizes

# 1) Xcode cleanup
bold "Step 1: Xcode cleanup"
if confirm "Delete Xcode DerivedData (safe – rebuilds on next build)?"; then
  rm -rf "$HOME/Library/Developer/Xcode/DerivedData"/* 2>/dev/null || true
  info "Deleted DerivedData."
else
  info "Skipped DerivedData."
fi

if confirm "Delete Xcode iOS DeviceSupport (safe – re-downloads as needed)?"; then
  rm -rf "$HOME/Library/Developer/Xcode/iOS DeviceSupport"/* 2>/dev/null || true
  info "Deleted DeviceSupport."
else
  info "Skipped DeviceSupport."
fi

if exists xcrun; then
  if confirm "Remove unavailable iOS Simulators (safe)?"; then
    xcrun simctl delete unavailable || true
    info "Removed unavailable simulators."
  else
    info "Skipped removing unavailable simulators."
  fi
else
  warn "xcrun not available; skipping simulator cleanup."
fi

if confirm "Delete ALL Simulator devices (recreates on demand; frees a lot)?"; then
  rm -rf "$HOME/Library/Developer/CoreSimulator/Devices"/* 2>/dev/null || true
  info "Deleted all simulator devices."
else
  info "Skipped full simulator reset."
fi

if [ -d "$HOME/Library/Developer/Xcode/Archives" ]; then
  if confirm "Delete Xcode Archives older than 60 days?"; then
    find "$HOME/Library/Developer/Xcode/Archives" -mindepth 1 -maxdepth 1 -type d -mtime +60 -print -exec rm -rf {} +
    info "Old archives deleted."
  else
    info "Skipped archive cleanup."
  fi
fi

# 2) Docker aggressive prune
bold "Step 2: Docker prune"
if exists docker; then
  docker system df || true
  if confirm "AGGRESSIVE: Remove ALL unused Docker images/containers/networks and volumes?"; then
    docker system prune -a --volumes -f || true
    info "Docker prune complete."
  else
    info "Skipped Docker aggressive prune."
  fi
else
  info "Docker not detected; skipping."
fi

# 3) Time Machine local snapshots
bold "Step 3: Time Machine local snapshots"
if exists tmutil; then
  tmutil listlocalsnapshots / || true
  if confirm "Thin Time Machine local snapshots by ~20GB (admin required)?"; then
    sudo tmutil thinlocalsnapshots / 20000000000 4 || true
  fi
  if confirm "Delete ALL remaining local snapshots (admin required)?"; then
    # Delete each listed snapshot id
    while IFS= read -r sid; do
      sid=${sid#com.apple.TimeMachine.}
      [ -n "$sid" ] && sudo tmutil deletelocalsnapshots "$sid" || true
    done < <(tmutil listlocalsnapshots / | sed -n 's/^com\.apple\.TimeMachine\.//p')
  else
    info "Skipped snapshot deletion."
  fi
else
  info "tmutil not available; skipping."
fi

# 4) iOS backups (optional)
bold "Step 4: iOS backups (optional)"
IOS_BACKUP_DIR="$HOME/Library/Application Support/MobileSync/Backup"
if [ -d "$IOS_BACKUP_DIR" ]; then
  du -sh "$IOS_BACKUP_DIR" || true
  if confirm "Delete iOS backup subfolders older than 120 days?"; then
    find "$IOS_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +120 -print -exec rm -rf {} +
    info "Old iOS backups deleted."
  else
    info "Skipped iOS backup cleanup."
  fi
else
  info "No local iOS backups directory found."
fi

# 5) Homebrew and caches (optional)
bold "Step 5: Homebrew and caches (optional)"
if exists brew; then
  if confirm "Run Homebrew cleanup and autoremove?"; then
    brew cleanup -s || true
    brew autoremove || true
    rm -rf "$HOME/Library/Caches/Homebrew"/* 2>/dev/null || true
    info "Homebrew cleanup done."
  else
    info "Skipped Homebrew cleanup."
  fi
fi

if confirm "Delete application caches larger than 1GB in ~/Library/Caches?"; then
  # Find top-level cache folders over ~1GB and delete
  CACHE_DIR="$HOME/Library/Caches"
  if [ -d "$CACHE_DIR" ]; then
    info "Candidates over 1GB:"
    # List and delete
    while IFS= read -r line; do
      size_mb=$(echo "$line" | awk '{print $1}')
      path=$(echo "$line" | cut -d$'\t' -f2-)
      if [ "$size_mb" -ge 1024 ]; then
        echo "Deleting $path (${size_mb}MB)"
        rm -rf "$path" || true
      fi
    done < <(du -sm "$CACHE_DIR"/* 2>/dev/null | sed $'s/\t/\t/')
  fi
else
  info "Skipped cache deletion."
fi

bold "===== AFTER ====="
print_sizes

bold "Done."
info "Empty Trash and restart to refresh Storage (‘System Data’) accounting."

