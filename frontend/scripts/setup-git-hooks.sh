#!/bin/sh

if git -C .. rev-parse --git-dir >/dev/null 2>&1; then
  git -C .. config core.hooksPath .githooks
fi
