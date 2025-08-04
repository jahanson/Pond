# Entity Learning: Future Enhancement for Pond

*This document captures ideas for dynamic entity recognition that emerged during development. These features are NOT part of the initial implementation but represent potential future enhancements.*

## Overview

Currently, Pond uses spaCy's pre-trained models for entity extraction. This works well for common entities (Google, Paris, Monday) but misses domain-specific entities (Sparkle, FastMCP, Claude) that are crucial to each AI's experience.

This document explores how Pond could evolve to learn entities dynamically from each AI's accumulated memories.

## The Problem

When an AI says "I debugged FastMCP with Sparkle," spaCy doesn't understand:
- **Sparkle** is a specific cat (not just any sparkle)
- **FastMCP** is a software library (not gibberish)
- These entities are meaningful within this AI's context

## Proposed Solution: Emergent Entity Recognition

### Core Concept

Each AI tenant would build their own "dictionary" of entities through pattern recognition:

1. Start with spaCy's general knowledge
2. Track frequently mentioned terms
3. Infer entity types from context
4. Build tenant-specific recognition rules
5. Apply learned knowledge to future memories

### How Learning Would Work

#### Stage 1: Pattern Detection
Track potential entities through:
- Frequency of mention (3+ times = candidate)
- Grammatical position (subject, object)
- Capitalization patterns
- Surrounding context

#### Stage 2: Type Inference
Determine entity type by analyzing:
- Associated verbs (stole, implemented, fixed → different entity types)
- Grammatical patterns (possessives, articles)
- Explicit mentions ("my cat Sparkle")
- Similarity to known entities

#### Stage 3: Confidence Building
```
First mention: "Sparkle" → unrecognized
3 mentions: "Sparkle" → unknown entity, tracking
10 mentions + patterns: "Sparkle" → likely PET/ANIMAL
Explicit confirmation: "Sparkle the cat" → confirmed CAT entity
```

#### Stage 4: Application
Once learned, apply to:
- Future entity extraction
- Improved search relevance
- Better splashback connections
- Richer memory relationships

## Technical Approach

### Database Schema
```sql
CREATE TABLE tenant_entities (
    tenant VARCHAR(100),
    entity_text TEXT,
    entity_type VARCHAR(50),
    confidence FLOAT,
    pattern_data JSONB,  -- grammatical patterns observed
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    mention_count INTEGER,
    confirmed BOOLEAN DEFAULT false,
    PRIMARY KEY (tenant, entity_text)
);
```

### Learning Pipeline

1. **Extraction Phase**: Use current spaCy pipeline
2. **Candidate Detection**: Track unrecognized capitalized terms
3. **Pattern Analysis**: Analyze grammatical context
4. **Confidence Scoring**: Build confidence through repetition
5. **Integration**: Add high-confidence entities to tenant's EntityRuler
6. **Feedback Loop**: Better extraction → better patterns → better learning

### Per-Tenant Entity Pipeline

Each tenant would have:
- Base spaCy model (shared)
- Custom EntityRuler with learned patterns
- Entity history and confidence scores
- Isolated from other tenants

## Integration with Splashback

Entity learning enhances splashback:
- Better entity recognition = better memory connections
- "Sparkle memories" cluster naturally
- Relationships emerge through shared entities
- AI develops "understanding" of its world

## Benefits

1. **Personalized AI Knowledge**: Each AI learns entities relevant to its experience
2. **Improved Memory Quality**: Better extraction = better search and connections
3. **Emergent Understanding**: AI's knowledge grows organically
4. **Domain Adaptation**: Technical AIs learn technical terms

## Implementation Considerations

### Performance
- Cache tenant pipelines
- Batch pattern analysis
- Periodic retraining, not real-time
- Balance memory vs accuracy

### Complexity
- Significant additional code
- Pattern analysis algorithms
- Confidence scoring systems
- Pipeline management

### Risks
- False positive learning
- Overfitting to early patterns
- Performance overhead
- Complexity explosion

## Example: Sparkle's Journey

1. **Day 1**: "Sparkle stole pizza" → No entity detected
2. **Day 7**: Multiple mentions → System notices pattern
3. **Day 14**: Behavioral patterns suggest animate entity
4. **Day 30**: "my cat Sparkle" → Confirms CAT type
5. **Day 90**: All Sparkle mentions properly tagged, rich splashback

## Future Research Questions

1. How many mentions before learning?
2. How to handle entity evolution (job changes, relationships)?
3. How to forget outdated entities?
4. How to handle conflicting patterns?
5. How to validate learned entities?

## Conclusion

While fascinating, this feature would add significant complexity to Pond. The current approach (using spaCy's pre-trained models + explicit tags) is sufficient for MVP.

This document preserves these ideas for potential future implementation when:
- Core Pond functionality is stable
- Performance requirements are clear
- Development resources are available
- User feedback indicates need

For now, we can achieve good results with:
- spaCy's pre-trained models
- User-provided tags
- Manual entity patterns in EntityRuler (if needed)

## Related Ideas

- Relationship extraction (who knows whom)
- Temporal entity tracking (when entities were relevant)
- Cross-tenant entity sharing (opt-in shared knowledge)
- Entity deprecation (forgetting old entities)