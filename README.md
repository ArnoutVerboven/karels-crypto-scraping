# karels-crypto-scraping

Repository for scraping Karel's Crypto from De Standaard newspaper weekly on Saturday using GitHub actions.

## Source

Crypto's are fetched from the following URLs:
- Last week's Crypto:
- This week's Crypto:

The key HTML fields are:


## Data format

The dataset is a list of Crypto's. Each Crypto consists of an ordered list of words, where each word has a cryptogram, a length, an array of help numbers (most empty), and index where the middle word intersects, and a solution (None for the Crypto latest Crypto of this week).

Two datasets are stored, one with the historical Crypto's with solutions, one with the latest without solution.
