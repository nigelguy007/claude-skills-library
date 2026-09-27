---
name: social_media_schema
description: Reference-only skill that defines canonical JSON schemas for classified output files. Includes enum warnings and dashboard detection rules.
---

# Social Media Schema Reference

Use this file as the canonical schema source for all classified outputs:

- `classified_rank.json`
- `classified_sentiment.json`
- `classified_trend.json`
- `classified_controversy.json`
- `classified_discovery.json`

If another skill instruction conflicts with this file, **this file wins**.

## Command Execution Note

This is a reference-only skill. There is no direct CLI command to run this skill.

- Use it by reading this schema before writing any `classified_*.json` output.
- Runnable commands belong to fetch/analysis/visualize skills (for example `sc-research research:deep "TOPIC"` and `sc-research visualize`).

---

## Dashboard Detection Rules

The web dashboard auto-detects which classified type a JSON file contains by checking for **unique field signatures**. If required fields are missing or misnamed, that tab will not appear.

| Classified Type | Detection Rule (fields checked)                             | Dashboard Tab       |
| --------------- | ----------------------------------------------------------- | ------------------- |
| **rank**        | `products` (array) AND `key_insights` (array)               | Product Rankings    |
| **sentiment**   | `distribution` (object) AND `by_source` (object)            | Sentiment Analysis  |
| **trend**       | `date_range` (object) AND `timeline` (array)                | Trend Timeline      |
| **controversy** | `overall_divisiveness` (string) AND `controversies` (array) | Controversy Map     |
| **discovery**   | `trending_topics` (array)                                   | Discovery Dashboard |

**These field names are non-negotiable.** Renaming, omitting, or nesting them differently will break dashboard detection.

---

## Enum Value Warnings

### SentimentLabel (Title Case — used in rank, sentiment, controversy contexts)

```
CORRECT: "Very Positive", "Positive", "Mixed", "Negative"
WRONG:   "very positive", "very_positive", "POSITIVE", "positive", "neutral"
```

`"neutral"` is NOT a valid SentimentLabel. Use `"Mixed"` instead.

### Divisiveness (Title Case — used in controversy)

```
CORRECT: "Low", "Medium", "High"
WRONG:   "low", "medium", "high", "LOW", "MEDIUM", "HIGH"
```

### Discovery sentiment (lowercase — DIFFERENT from SentimentLabel)

```
CORRECT: "positive", "negative", "neutral", "mixed"
WRONG:   "Positive", "Negative", "Neutral", "Mixed", "Very Positive"
```

Discovery is the ONLY type that uses lowercase sentiment and includes `"neutral"`.

### Discovery platform (lowercase)

```
CORRECT: "reddit", "x"
WRONG:   "Reddit", "X", "twitter", "Twitter"
```

### Key Moment significance (lowercase — used in trend)

```
CORRECT: "high", "medium", "low"
WRONG:   "High", "Medium", "Low"
```

### Quote context (lowercase — used in rank)

```
CORRECT: "pro", "con", "general"
WRONG:   "Pro", "Con", "General"
```

---

## Canonical Type Definitions

```typescript
// === RANK (classified_rank.json) ===
// Dashboard detects via: products + key_insights

export interface ClassifiedData {
  topic: string;
  source_file?: string;
  products: Product[]; // REQUIRED for dashboard detection
  key_insights: string[]; // REQUIRED for dashboard detection
}

export interface Product {
  rank: number;
  name: string;
  sentiment: SentimentLabel; // Title Case: "Positive", "Mixed", etc.
  mentions: number;
  estimated_engagement_score: number;
  consensus: string;
  pros: string[];
  cons: string[];
  highlight_quotes: Array<{
    text: string;
    author: string;
    link: string;
    context?: "pro" | "con" | "general"; // lowercase
  }>;
}

export type SentimentLabel =
  | "Positive"
  | "Negative"
  | "Mixed"
  | "Very Positive";

// === SENTIMENT (classified_sentiment.json) ===
// Dashboard detects via: distribution + by_source

export interface SentimentData {
  topic: string;
  overall_mood: SentimentLabel;
  distribution: {
    // REQUIRED for dashboard detection
    very_positive: number; // snake_case keys, not camelCase
    positive: number;
    mixed: number;
    negative: number;
  };
  by_source: {
    // REQUIRED for dashboard detection
    reddit: SourceSentiment;
    x: SourceSentiment;
  };
  product_sentiments: ProductSentiment[];
}

export interface SourceSentiment {
  very_positive: number;
  positive: number;
  mixed: number;
  negative: number;
}

export interface ProductSentiment {
  name: string;
  overall: SentimentLabel;
  reddit_sentiment: SentimentLabel | null;
  x_sentiment: SentimentLabel | null;
  evidence_quotes: Array<{
    text: string;
    author: string;
    link: string;
    sentiment: SentimentLabel; // Title Case
  }>;
}

// === TREND (classified_trend.json) ===
// Dashboard detects via: date_range + timeline

export interface TrendData {
  topic: string;
  date_range: {
    // REQUIRED for dashboard detection
    from: string;
    to: string;
  };
  granularity?: "day" | "week" | "month";
  timeline: TimelinePoint[]; // REQUIRED for dashboard detection
  key_moments: KeyMoment[];
}

export interface TimelinePoint {
  period: string; // Format depends on granularity (see worker skill)
  post_count: number;
  total_engagement: number;
  reddit_posts: number;
  x_posts: number;
}

export interface KeyMoment {
  date: string;
  event: string;
  significance: "high" | "medium" | "low"; // lowercase
  url?: string;
}

// === CONTROVERSY (classified_controversy.json) ===
// Dashboard detects via: overall_divisiveness + controversies

export interface ControversyData {
  topic: string;
  overall_divisiveness: "Low" | "Medium" | "High"; // REQUIRED + Title Case
  controversies: Controversy[]; // REQUIRED for dashboard detection
}

export interface Controversy {
  topic: string;
  heat_score: number; // 0-100
  divisiveness: "Low" | "Medium" | "High"; // Title Case
  side_a: ControversySide;
  side_b: ControversySide;
}

export interface ControversySide {
  position: string;
  supporter_count: number;
  sample_quotes: Array<{
    text: string;
    author: string;
    link: string;
  }>;
}

// === DISCOVERY (classified_discovery.json) ===
// Dashboard detects via: trending_topics

export interface DiscoveryData {
  topic: string;
  period: string;
  total_posts_analyzed: number;
  trending_topics: DiscoveryTopic[]; // REQUIRED for dashboard detection
}

export interface DiscoveryTopic {
  id: string;
  topic_name: string;
  description: string;
  category: string;
  engagement_score: number;
  sentiment: "positive" | "negative" | "neutral" | "mixed"; // lowercase!
  key_posts: KeyPost[];
  highlight_comments: Array<{
    text: string;
    author: string;
    link: string;
    platform: "reddit" | "x"; // lowercase
  }>;
}

export interface KeyPost {
  title: string;
  url: string;
  platform: "reddit" | "x"; // lowercase
  engagement: number;
  thumbnail?: string;
}
```
