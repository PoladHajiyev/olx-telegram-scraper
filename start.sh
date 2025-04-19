#!/bin/bash

# Step 1: Install the Chromium browser for Playwright
python3 -m playwright install chromium

# Step 2: Run your Python scraper
python3 main.py
