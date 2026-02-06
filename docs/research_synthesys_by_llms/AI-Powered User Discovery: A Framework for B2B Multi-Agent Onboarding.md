# AI-Powered User Discovery: A Framework for B2B Multi-Agent Onboarding

The most effective AI-powered onboarding systems combine **parallel background research** with **adaptive conversational discovery** to build rich user profiles in under ten minutes. This framework synthesizes product discovery methodologies, interview best practices, and AI implementation patterns into a practical blueprint for B2B professionals.

## Why traditional onboarding falls short

Most onboarding systems suffer from a fundamental tension: asking too many questions feels invasive and slow, while inferring too much feels presumptuous and often wrong. The research reveals a third path—**orchestrated discovery** that runs intelligent background analysis while conducting an adaptive interview that follows the user's natural conversational flow.

The Jobs-to-Be-Done framework provides the theoretical foundation: users don't want your product, they want to make progress in their lives. Clayton Christensen's formulation—"When [situation], I want to [motivation], so I can [expected outcome]"—becomes the north star for discovery. Every question and inference should illuminate what "job" the user is hiring your AI tool to accomplish.

The constraint of **10 minutes** forces ruthless prioritization. Research on rapid user interviews shows this timeframe can yield substantial insights when properly structured: 1-2 minutes for context establishment, 5-6 minutes for adaptive exploration, and 1-2 minutes for synthesis and next steps.

## The dual-track discovery architecture

The framework operates on two parallel tracks that converge into a unified user profile:

**Track 1: Background Research (automated, 60-120 seconds)**
Processes user-provided links (LinkedIn, company website, Notion/Obsidian documents) to build preliminary context before and during the conversation. Modern LLM APIs enable comprehensive analysis within 2 minutes through parallel processing:

- LinkedIn profile analysis extracts role, seniority, industry, career trajectory, skills, and professional interests in **5-15 seconds**
- Company website analysis identifies organization size, industry vertical, tech stack, and business priorities in **10-20 seconds**  
- Knowledge base documents (Notion, Obsidian) reveal working style, organizational preferences, and project priorities in **30-60 seconds** depending on volume
- Knowledge graph construction synthesizes cross-source entities and relationships in **30-60 seconds**

**Track 2: Conversational Interview (adaptive, 8-10 minutes)**
While background analysis runs, an AI interviewer conducts a semi-structured conversation that starts with predictable questions but adapts based on user responses. The interview follows the "funnel technique"—broad questions narrow systematically while probing reveals underlying needs.

## What the background research reveals

Each data source provides distinct value for personalization:

**LinkedIn profiles** surface professional identity signals: current role and headline reveal how users position themselves; career trajectory shows whether they're climbing, pivoting, or settling; skills and endorsements indicate expertise depth; content engagement patterns suggest thought leadership interests. The most valuable inference is **seniority-adjusted communication calibration**—an individual contributor needs different framing than a VP.

**Company websites** reveal organizational context through technology stack detection (tools like Wappalyzer identify CMS, analytics, marketing automation in seconds), company size and stage indicators, and job postings that expose growth priorities and technical challenges. For B2B personalization, combining **role + tech stack** enables precise product positioning.

**Knowledge base documents** expose working style and methodology in ways users rarely articulate directly. Notion database structures reveal whether users think in Kanban boards (agile-oriented), timelines (project-focused), or nested pages (detailed thinkers). Obsidian vault organization—particularly graph density and backlink patterns—indicates whether someone is a collector, synthesizer, or action-oriented thinker. Heavy template usage signals systematization preferences; sparse organization suggests flexibility preference.

The synthesis approach uses **entity extraction and relationship mapping** across sources, creating a knowledge graph that connects role → projects → tools → challenges → goals. This enables personalization that feels contextual rather than surveillance-like.

## The conversational discovery methodology

The interview methodology draws from three complementary frameworks:

**Jobs-to-Be-Done interviews** focus on understanding the "timeline"—what triggered the user's search for a solution, what alternatives they considered, what anxieties remain about adoption. The key insight: past behavior predicts future behavior far better than stated preferences. "Tell me about the last time you faced this problem" yields more actionable data than "Would you use this feature?"

**The Mom Test** (Rob Fitzpatrick) provides the questioning discipline: talk about their life, not your product; ask about specifics in the past, not generics about the future; talk less, listen more. The target is **80% user talk time**. Three types of "fluff" to probe past: generic claims ("I usually..."), future promises ("I would definitely..."), and compliments ("That sounds great!").

**Teresa Torres' Continuous Discovery** adds the Opportunity Solution Tree structure: define desired outcomes, map opportunities (unmet needs, pain points), then brainstorm solutions. For onboarding, this means identifying not just what users want to do, but what outcomes they're actually trying to achieve—and what's currently blocking them.

## Adaptive interview design principles

The interview starts structured but becomes conversational through **semi-structured interview design**. The first 2-3 questions follow a predetermined script to establish baseline context; subsequent questions adapt based on responses.

The adaptation logic follows clear signals:

**Probe deeper when users express:**
- Subjective words (frustrated, annoyed, excited, confused)
- Vague phrases ("It was fine," "kind of annoying")
- Incomplete answers missing context or reasoning
- Contradiction with earlier statements
- Pain point language ("struggle," "can't," "problem")
- Unmet need markers ("wish," "if only," "would be nice")

**Move on when:**
- Same information repeats (saturation reached)
- Clear, complete answer with specific examples provided
- User struggles to add new information
- Time constraints require covering other essential topics

The **TEDW framework** provides reliable follow-up phrases: Tell me more about [X], Explain what you mean by [X], Describe [experience], Why/Walk me through. These can be implemented directly in AI prompt engineering.

For **voice-based discovery** (STT/TTS), the critical constraint is latency—sub-3-second round-trip time maintains conversational flow. Modern architectures achieve this through parallel processing (STT partials <150ms, model response <300ms, TTS first byte <200ms) and strategic silence handling. Voice discovery increases engagement but requires barge-in detection so the AI stops speaking when users interrupt.

## The 10-minute session structure

Based on the research, here is the recommended time allocation and question flow:

**Phase 1: Context Establishment (Minutes 0-2)**

*Automated actions:* Begin background research on provided links immediately.

*Structured questions (choose 2):*
- "How would you describe your role and what you're primarily responsible for?"
- "What does a successful week look like for you in this role?"
- "What brought you to explore [tool category] right now?"

*Purpose:* Establish baseline identity, confirm or correct background research inferences, identify immediate context.

**Phase 2: Core Discovery (Minutes 2-7)**

*Automated actions:* Background research completes (~60-90 seconds); insights begin informing question selection.

*Semi-structured exploration (2-3 questions plus probes):*
- "Tell me about a recent time when [relevant task based on role/context] was particularly challenging."
- Follow probes: "What made it hard?" "What did you try?" "What would have helped?"
- "What's the first problem you're hoping an AI assistant can help solve?"
- "When you imagine this tool being indispensable to you, what's happening?"

*Adaptive branching:* If background research reveals specific tools/workflows, probe: "I noticed you use [Notion/Asana/specific tool]. How does that fit into your workflow?" If user mentions frustration, apply laddering: "Tell me more about what was frustrating → What happened as a result → Why does that matter to your team?"

*Purpose:* Uncover the "job to be done," identify pain points, understand current workarounds, assess emotional and social dimensions of needs.

**Phase 3: Synthesis and Closing (Minutes 7-10)**

*Structured questions:*
- "Based on what you've shared, it sounds like [paraphrase key points]. Does that capture it?"
- "What else should I understand about your situation that I haven't asked about?"
- "If you had to pick one thing you want this tool to nail, what would it be?"

*Purpose:* Validate understanding, catch blind spots, identify single highest-priority need, create closure.

## Building the persistent user profile

The user profile should serve multiple specialized agents while maintaining a coherent whole. Research on multi-agent architectures recommends a **hierarchical model**:

**Global Profile (accessible by all agents):**
- Core identity: name, role, organization, industry
- Communication preferences: format (bullets vs. prose), tone (formal vs. casual), detail level
- Primary constraints: time sensitivity, confidentiality requirements

**Domain-Specific Profiles (filtered by agent type):**
- Research Agent: domain expertise, current projects, industry context
- Writing Agent: communication style, tone, terminology preferences, past work samples  
- Data Agent: technical skills, tools used, data format preferences
- Coordination Agent: full profile for routing decisions

**Session Context (ephemeral):**
- Current task state
- Recent conversation highlights
- Active project details

Each profile field should include **confidence metadata**: source (explicit vs. inferred), confidence score (0-1), evidence references, and last validated date. The decision logic: confidence <0.5 triggers clarifying questions; 0.5-0.8 applies with fallback options; >0.8 applies confidently.

## Prioritizing key needs versus nice-to-haves

The JTBD framework categorizes needs across three dimensions:

**Functional jobs:** Practical tasks users want to accomplish ("Generate accurate reports quickly")

**Emotional jobs:** How users want to feel ("Feel confident presenting to leadership")

**Social jobs:** How users want to be perceived ("Be seen as technically proficient by colleagues")

For prioritization, apply the **Impact-Effort Matrix**: high-impact/low-effort needs are quick wins to address immediately; high-impact/high-effort needs are big bets requiring planning; low-impact items go to the backlog. The MoSCoW method (Must/Should/Could/Won't) provides additional structure.

Key signals indicating high-priority needs:
- Frequency of mention during discovery
- Severity of pain language used
- Workarounds currently employed (workarounds = strong signal)
- Impact on critical business outcomes
- Alignment with stated goals

## Profile evolution over time

Profiles should update through both explicit and implicit mechanisms:

**Explicit updates:** User directly states preferences ("Remember that I prefer bullet points"), structured periodic check-ins, settings management.

**Implicit learning:** Behavioral patterns (response format preferences learned from regeneration requests), feedback interpretation (thumbs up/down signals), interaction style analysis over time.

**Update frequencies:**
- Real-time: Explicit user corrections and statements
- Session-based: Behavioral patterns and workflow observations
- Periodic (daily/weekly): Synthesis of accumulated signals
- Event-triggered: Major project changes, role transitions

Following Claude's architecture approach, profiles should be **transparent and editable**—users can view, edit, export, and delete what the system knows about them. This builds trust and enables correction of wrong inferences.

## Privacy and ethical implementation

Processing user-provided data requires clear consent architecture:

**Consent requirements:** Freely given (not bundled with essential services), specific (separate consent per processing purpose), informed (clear explanation of what/why/how), unambiguous (clear affirmative action), and withdrawable (easy to revoke).

**Recommended consent flow:**
1. Pre-analysis notice explaining what will be analyzed
2. Specific disclosure listing exact data types and purposes
3. Granular options allowing selective consent (e.g., LinkedIn yes, documents no)
4. Processing explanation connecting analysis to personalization benefits
5. Clear withdrawal option with accessible settings link

**Transparency implementation:**
- Show users what was extracted: "We identified you as a Product Manager in fintech"
- Explain personalization: "Based on your profile, we're highlighting these features..."
- Provide correction mechanism: "Is this correct? Update your preferences"
- Maintain audit trail of what was processed and when

## Question bank for implementation

**Opening questions (choose 1-2):**
- "What's the hardest part about [domain area] for you right now?"
- "Tell me about the last time you [relevant action based on role]."
- "What are you currently doing to [achieve primary goal]?"

**Probing questions (use 2-3 as adaptive follow-ups):**
- "Can you walk me through that?"
- "Why was that challenging?"
- "What happened next?"
- "Who else was affected by this?"
- "What did you try to solve it?"

**Depth questions (choose 1-2 to uncover underlying needs):**
- "Why is solving this important to you and your team?"
- "What would change if this problem went away?"
- "What have you tried before that didn't work?"

**Closing questions (choose 1):**
- "What else should I understand that I haven't asked about?"
- "If you could change one thing about how you [do X], what would it be?"
- "What would make you say 'this tool really gets me' after our first week together?"

## Key metrics to track

- **Profile completeness:** Percentage of core fields populated after onboarding
- **Inference accuracy:** Rate at which inferred preferences are corrected by users
- **Talk-time ratio:** Target 80%+ user speaking time
- **Time-to-personalization:** How quickly relevant personalization appears
- **Discovery depth:** Number of "why" levels reached (surface → consequence → value)
- **User satisfaction:** Post-onboarding sentiment on "does this tool understand me?"

## Synthesis: the complete discovery session

A well-executed 10-minute AI discovery session orchestrates three concurrent processes:

1. **Background intelligence** silently analyzes LinkedIn, company website, and shared documents during the first 90 seconds, progressively enriching the AI's contextual awareness

2. **Adaptive conversation** follows the funnel pattern from broad context-setting through targeted probing, adapting question selection based on both user responses and emerging background insights

3. **Profile construction** continuously synthesizes explicit statements and implicit signals into a structured profile with confidence-weighted fields

The output is a persistent user profile that enables any agent in the multi-agent system to provide contextually relevant assistance from the first interaction—while remaining transparent, editable, and privacy-respecting.

The core principle: **discovery should feel like a productive conversation, not an interrogation**. By running intelligence in the background while conducting an empathetic, adaptive interview, the system builds rich understanding while respecting the user's time and creating immediate value. The goal isn't just to know about users—it's to help them make progress on the jobs they're hiring your AI tool to do.