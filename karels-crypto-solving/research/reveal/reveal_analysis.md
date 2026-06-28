# Letter-reveal sweep (randomized reveals, by word length)

Reveal = fraction of letters uncovered at random positions (nested). Each cell = accuracy; `n` per (length x reveal) cell is roughly per-bucket size.

### gpt-5-mini-2025-08-07 (n=150, effort=low, cost $1.01)

| length \ reveal | 0% | 25% | 50% | 75% |
| --- | ---: | ---: | ---: | ---: |
| 3-4 | 37% | 67% | 83% | 90% |
| 5-6 | 40% | 70% | 73% | 93% |
| 7-8 | 13% | 40% | 57% | 80% |
| 9-10 | 7% | 40% | 60% | 90% |
| 11+ | 13% | 23% | 63% | 77% |
| **overall** | 22% | 48% | 67% | 86% |

### gpt-5-2025-08-07 (n=150, effort=low, cost $8.19)

| length \ reveal | 0% | 25% | 50% | 75% |
| --- | ---: | ---: | ---: | ---: |
| 3-4 | 50% | 77% | 93% | 97% |
| 5-6 | 63% | 77% | 83% | 93% |
| 7-8 | 37% | 57% | 87% | 100% |
| 9-10 | 27% | 67% | 77% | 90% |
| 11+ | 27% | 57% | 80% | 87% |
| **overall** | 41% | 67% | 84% | 93% |

### gpt-4.1 (n=150, effort=low, cost $1.50)

| length \ reveal | 0% | 25% | 50% | 75% |
| --- | ---: | ---: | ---: | ---: |
| 3-4 | 20% | 43% | 73% | 90% |
| 5-6 | 33% | 40% | 63% | 80% |
| 7-8 | 13% | 30% | 37% | 63% |
| 9-10 | 7% | 20% | 57% | 77% |
| 11+ | 3% | 7% | 37% | 60% |
| **overall** | 15% | 28% | 53% | 74% |

Total estimated cost: $10.70
