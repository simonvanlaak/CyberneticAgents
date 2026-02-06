LLM Agents for Autonomous Interviews: State of Research and Development
Introduction

Advances in large language models (LLMs) have enabled a new class of autonomous interview agents that can conduct interviews without human moderators. These AI interviewer agents are being explored in both user research (product discovery) and hiring (job interviews). By leveraging LLMs’ conversational abilities, such agents can ask questions, probe deeper with follow-ups, and even analyze responses – all at a scale and consistency difficult for human interviewers to achieve. Researchers and companies are now experimenting with both text-based chatbots and voice-based AI interviewers (often with text-to-speech and speech recognition) to carry out semi-structured interviews. Below, we provide a comprehensive overview of the current state of this technology in the two domains, highlight academic studies and commercial tools, and discuss key technical challenges, capabilities, and limitations. We also compare AI-led interviews with traditional human-led interviews to understand their strengths and weaknesses.
LLM Interviewers in User Research and Product Discovery

User experience researchers are adopting LLM-powered agents to conduct customer interviews for product feedback, concept testing, and other discovery research. Traditionally, teams faced a trade-off between scale and depth – fast surveys yielded shallow insights, while in-depth interviews were slow and resource-intensive. AI interviewers promise to “conduct high-quality, qualitative interviews with the speed and scale of surveys”, potentially breaking this trade-off.
Academic Research on AI-Moderated UX Interviews

Recent research demonstrates that LLM agents can successfully moderate semi-structured user interviews. For example, Liu et al. (2025) developed CLUE-Interviewer, an LLM-powered UX interviewer that automatically interviewed users about their experience with various chatbots. Following best practices for user interviews, CLUE-Interviewer was prompt-engineered to cover key topics (e.g. understanding, meeting user needs, credibility) and to ask follow-up questions for deeper insight. In a study with 1,206 interviews, CLUE-Interviewer asked at least one follow-up in over half of the sessions (averaging 1.3 follow-up questions) instead of just sticking to a script. Human evaluators found that the AI interviewer successfully behaved like a UX researcher: it covered ~74% of the target topics from the discussion guide and actively probed for clarification or detail. These in-the-moment interviews, conducted right after users’ chatbot interactions, elicited detailed feedback that pure rating surveys would miss. Notably, the automated interviewer referenced the user’s prior chat context to make the conversation feel contextual and “in-the-moment”.

Another striking example is Anthropic’s AI Interviewer (2025), which conducted 1,250 extensive interviews with professionals about their AI usage. Anthropic built a Claude-powered agent to run detailed, hour-plus interviews and feed results to human researchers. This approach enabled them to gather nuanced qualitative data at a massive scale that would be impractical with human interviewers alone. Similarly, Stanford researchers Park et al. (2025) used an AI interviewer to conduct 2-hour life-story interviews with 1,052 individuals for a social simulation study. The AI interviewer asked open-ended questions about the participants’ life experiences and views on controversial issues, following up based on each answer. This standardized yet adaptive approach let one graduate student’s team collect rich ethnographic data from over a thousand people, something traditionally requiring enormous time. These studies show that LLM-driven agents can handle complex qualitative interviews – even sensitive, open-ended ones – by dynamically adjusting questions and exhibiting basic conversational rapport. Early research suggests that with careful prompt design (e.g. instructing the AI to be empathetic, culturally sensitive, and to probe like a skilled interviewer), chatbots “might mimic the behavior of a skilled interviewer…asking relevant follow-up questions and maintaining structure” without the inconsistencies or biases a human might introduce.

Crucially, initial evidence indicates participants may be surprisingly candid with AI interviewers. According to venture firm Greylock, whose team tested various AI research tools, “participants generally share more when speaking with an AI than with a human”. One hypothesis is that people feel less judged by an impartial AI, fostering honesty on potentially critical or sensitive feedback. This increased openness can be a boon for user research, which relies on candid user opinions. On the other hand, researchers note that AI interviewers must be designed to uphold ethical standards and trust, ensuring participants know how their data is used and feel comfortable with the AI moderator (e.g. having disclaimers that it’s an AI and that their responses are confidential). Both the CLUE and Anthropic projects obtained informed consent and IRB oversight for interviews, highlighting that human research ethics still apply when an AI conducts the questioning.
AI-Driven User Interview Platforms and Startups

The promise of on-demand, AI-led user interviews has given rise to a wave of startups and tools. These platforms advertise the ability to replace or augment traditional UX research by having AI “moderators” conduct interviews and instantly analyze results. A recent industry analysis noted this is an emerging “greenfield category” – many organizations cannot even name one vendor yet – but dozens of AI-native research tools are now entering the market. Below is a summary of notable developments:

    Listen Labs – An “AI-first research platform” offering AI-moderated interviews at scale. Listen’s chatbot interviewer engages users in personalized interviews with each customer, at scale (as a replacement for live interviews, surveys, and focus groups). The platform supports multiple modalities – users can respond via text, audio, or video – and over 100 languages with automatic translation. After each interview, Listen generates instant insights (e.g. key takeaways, themes, personas) using AI analysis. By automating recruiting (access to a pool of participants) and analysis, Listen compresses what once took days of manual work into a fast, self-service workflow. According to customer case studies, companies have been able to collect rich user stories “within a day” using the AI interviewer.

    Outset.ai – A well-funded startup (backed by a recent $30M Series B) that markets itself as “the most advanced AI-moderated research platform.” Outset’s AI interviewer uses dynamic probing to “reveal the ‘why’ behind consumer preferences at scale”. It can ask follow-up questions in response to participant answers, much like a human moderator, to dig into motivations. The goal is to provide qualitative depth with quantitative speed. Outset emphasizes that teams can “go deep, at scale” and keep their research lean by letting “customizable AI-moderators do the heavy lifting from running interviews to compiling insights.”. This points to a trend: these tools not only conduct the interviews, but also automate transcription, thematic analysis, and even slide-ready reports.

    Strella (strella.io) – An AI-powered customer research platform that invites teams to “run 100 customer interviews by tomorrow morning.” Strella’s AI conducts in-depth interviews and generates actionable insights in just a few hours. It guides users through the full process: automatically generating a “discussion guide” (interview questionnaire) tailored to your research goals, recruiting participants that meet specified criteria (with built-in panel and filters), and then executing AI-moderated interviews that dig deep. Strella’s interface shows the AI picking up on a participant’s phrase and asking a follow-up – e.g., when a user said an accounting process “is not perfect,” the AI interviewer asks, “You mentioned ‘not perfect’... can you tell me more about what that looks like? What happens when the system breaks down or feels frustrating?”. This mimics a skilled interviewer’s tactic of probing an interesting remark. Afterward, Strella clusters responses and surfaces key themes across interviews (e.g. grouping users by motivation or need). Such auto-analysis addresses the biggest bottleneck after interviews: synthesizing mountains of qualitative data.

    Convo (getconvo.ai) – (Also branded as Conveo) A YC-backed platform calling itself “the only AI interviewer that captures every human signal.” It not only chats with participants but also analyzes voice tone, video, facial expressions, and even objects/behavior in video in real-time. The AI “co-worker” designs the study, interviews real people (asynchronously via a chat or video interface), then instantly analyzes the recordings to produce insights. By capturing non-verbal cues and employing computer vision (for body language), Convo aims to approach the richness of a face-to-face interview. This reflects a technical push to incorporate multimodal LLM agents that don’t just see text, but can “see” and “hear” the participant, allowing analysis of emotions or engagement level. Convo’s focus on video interviews also suggests use-cases like concept tests where a user might be on camera reacting to a prototype, and the AI interviewer can observe their reactions as well as their words.

    Maze, a UX research platform, has integrated AI to enable automated user interviews. Maze’s blog notes that “AI can easily conduct moderated and unmoderated research solo” – from generating tailored questions to actually “moderating interviews and analyzing responses” without human intervention. The industry is moving toward a hybrid research model, where AI handles the repetitive heavy-lifting (scheduling, asking baseline questions, transcribing, initial thematic coding) and human researchers focus on higher-level synthesis and strategic questions. Notably, practitioners emphasize that AI will not replace human researchers entirely, but rather free them from rote tasks to concentrate on design, empathy, and interpretation. In fact, some UX teams now treat AI as a “co-pilot”: it may conduct a first round of interviews to quickly map out broad patterns, which the human team then follows up on with targeted live interviews or uses to inform product decisions more rapidly.

    Other entrants: A number of other AI-native research tools have sprung up, often with similar capabilities. For instance, Reforge Research’s AI Interviewer (from a product strategy education company) can identify users, conduct realistic, conversational audio interviews with them on demand, and instantly integrate the transcripts into analysis dashboards. It touts combining “survey scale” with “interview depth”, echoing the common value prop. Voice-based interview agents are also emerging: some platforms offer phone-call style AI interviews for users who prefer speaking to typing, leveraging advanced speech recognition and natural sounding text-to-speech voices. The Greylock report includes startups like VoicePanel and Beheard that likely specialize in voice interviews at scale (e.g. automatically calling users for feedback). Major user research vendors are also adding AI features – for example, UserTesting (a traditional platform) has begun to experiment with AI summarization of interview videos, while Qualtrics and others explore chatbot surveys.

Overall, user research interview agents are becoming viable thanks to LLMs’ improved reasoning and language abilities. Modern models can handle nuanced follow-ups and “probe, clarify, and ask follow-up questions like a real researcher would”. This unlocks deeper insights than static Q&A bots of the past. Crucially, voice-capable models (combined with speech AI) let these agents converse naturally, not just via text – an important step for qualitative research where tone and fluid conversation matter. Early adopters report significant efficiency gains: teams can conduct dozens of interviews in the time it used to take to schedule and complete one or two, and in many cases the frequency of research increases (e.g. what might have been a quarterly study can become a weekly ongoing check-in). However, practitioners are learning when to use AI vs human: straightforward exploratory questions or concept tests may be handled by AI alone, whereas high-stakes strategic research or usability testing of very complex interfaces might still need a human’s touch. In many cases, a hybrid approach is favored – AI does an initial round or works in tandem with a human moderator (for example, an AI could sit in on a human-led interview to suggest live follow-up questions or to annotate and analyze in real-time, acting as a “silent research assistant”).
LLM Agents in Hiring and Job Interviews

The job interview domain has also seen the rise of AI interviewer agents, though the context and goals differ from user research. In recruitment, AI interviews are typically used to screen and evaluate candidates in early rounds, or to provide interview practice and feedback. Many organizations already use AI in parts of the hiring funnel (e.g. résumé screening, assessment scoring), and now conversational agents are being deployed to conduct actual interviews or Q&A sessions with candidates. According to the World Economic Forum, 88% of companies are using AI to initially screen candidates in some form. This includes parsing resumes and also automated interviews where an AI poses questions and evaluates responses. Below, we explore the developments in AI-led job interviews:
AI-Powered Screening Interviews and Chatbots

For high-volume hiring, companies have turned to asynchronous video interviews and text-based chatbots to handle the first interaction. One common format is the one-way video interview: candidates record video answers to preset questions, which are then analyzed by AI or reviewed by humans later. While these are not fully interactive agents (there’s no dynamic back-and-forth), they set the stage for AI evaluation. Candidates often find one-way videos awkward – essentially “a front-facing camera of myself…with no feedback”, as one student described. The lack of an interviewer can cause a “feedback void” where candidates feel unsure if they’re responding well. To make this experience more engaging (and scalable), some companies are introducing AI avatars or chatbots to simulate an interviewer in real time.

For example, candidates have reported doing interviews where an AI-generated avatar asks questions, or a text chatbot conducts a structured interview and transcribes their answers. One such system is Mya (a.k.a. “Maya”), an AI recruiting chatbot that several companies have used for screening. In these interviews, “AI interview chatbots, like Maya, are being used to screen job candidates and will parse an interviewee’s answers much like how it would read a resume — looking for keywords, concepts and phrases.”. The chatbot asks a series of questions about the candidate’s experience or situational judgments; the underlying AI then evaluates the responses for relevant skills, certain lexical choices, and sentiment (e.g. positive framing vs. negative tone). Recruiters note that an AI might flag if a candidate speaks very negatively (e.g. “trashing a former employer” could be scored lower by the algorithm). Essentially, the chatbot is scoring how well the answers align with the job criteria, much as human screeners do, but in an automated way. The advantage is consistency and speed: every candidate gets the same initial questions delivered in the same manner, and the AI can handle thousands of interviews simultaneously at any hour. The disadvantage is that candidates may feel they’re talking into a void or be concerned about how their answers are interpreted with no human nuance. Career coaches advise candidates to adapt to these AI interviews by using clear “STAR” structured answers (Situation, Task, Action, Result) and including the right keywords, to ensure the AI picks up on relevant qualifications. In other words, candidates now must “interview for the algorithm” to some extent – a stark contrast to tailoring one’s interpersonal chemistry for a human interviewer.

On the hiring company side, a number of HR tech products provide AI interview solutions:

    Sapia.ai (formerly PredictiveHire) – A leading AI interview platform that offers a chat-based interview followed by automated scoring and feedback. Candidates engage in a text chat answering behavioral questions, usually on their own time. Sapia’s system then evaluates these responses with a proprietary language model that infers traits and competencies. Uniquely, Sapia emphasizes transparency and fairness: their “powerful scoring engine explains its reasoning with detailed candidate insights,” providing “understandable, auditable AI interviewing at scale.”. In practice, this means recruiters receive a report on each candidate with scores for various competencies (e.g. communication, teamwork) along with excerpts from the candidate’s text that support the scores, so they can see why the AI scored someone a certain way. Sapia also claims to follow an “FAIR™ Hiring” framework to mitigate bias, and advertises itself as “the original ethical AI interview platform”. The results they report are impressive: across millions of candidate interviews conducted, they cite a 90% candidate satisfaction rate and significant reductions in time-to-hire and early attrition. In Sapia’s case studies, companies like retail chains saw their hiring process speed up by 50% and turnover drop ~89%, purportedly due to better candidate-job fit identified by the AI. Such metrics suggest that when carefully deployed (and combined with workflow integration, as Sapia does with ATS partnerships), AI interviews can improve efficiency without alienating candidates – though the claim of 90% satisfaction indicates many candidates actually appreciate the faster, on-demand interview format.

    Paradox (Olivia) – Paradox.ai offers an AI assistant named Olivia, widely used for recruiting. While Olivia’s primary functions are conversational scheduling and answering candidate FAQs, it also conducts initial screening chats. In a typical use, a candidate might encounter Olivia on a company’s careers site, answer a few questions about their experience or availability in a chat, and even do a quick Q&A relevant to the role. Olivia then either progresses the candidate (e.g. schedules them for a human interview if they meet criteria) or courteously disqualifies them. The emphasis here is on efficiency and a friendly candidate experience (“every great hire starts with hello” is Paradox’s tagline). Many high-volume employers (hospitality, retail) use such AI chat screening to handle applications instantly rather than having people wait weeks for a response.

    HireVue and Automated Video Interviews – HireVue is known for video interviewing tools and had developed AI analysis that evaluates recorded interview videos. Historically, HireVue’s AI would analyze not just the content of answers but also facial expressions, tone, and microgestures to predict job performance – a highly controversial practice that raised bias and transparency concerns. Under pressure (including academic criticism and regulatory scrutiny), HireVue dropped the facial analysis component by 2021, focusing instead on transcribed speech analysis. Today, HireVue and similar platforms still use AI to rate candidates’ video answers based on language and sometimes audio cues, providing recruiters with an AI-recommended score or rank. This is a semi-AI interviewer scenario: the interview questions may be predetermined, but the AI “listens” to the candidate’s spoken answers and evaluates them as a human might. However, because candidates are speaking to a camera, the experience can be isolating. Experts recommend candidates practice these one-way interviews to maintain energy and eye contact, since “that complete lack of feedback can really throw some people” unfamiliar with the format. We are also seeing the emergence of AI interview coaching tools (e.g. platforms that simulate an interviewer and then give the user feedback on their performance). While not part of the company’s hiring process, these use LLMs to help job-seekers prepare by acting as a mock interviewer that can critique answers and suggest improvements, often using the same criteria real AI hiring tools would.

Autonomous Interview Agents for Deeper Evaluation

Beyond initial screenings, researchers and some companies are experimenting with more comprehensive AI-conducted interviews that evaluate a candidate’s skills and provide detailed feedback or scoring. One example is the system described by Yazdani et al. (2025) called Zara, an LLM-based recruiter agent deployed on the micro1 hiring platform. Zara goes further than just chat screening: it “conducts conversational AI-led interviews tailored specifically to evaluate a candidate’s technical and interpersonal skills for the targeted job role” and then “autonomously generates structured post-interview evaluations based on the candidate’s performance”. In practice, candidates applying via micro1 first chat with Zara in a live interview: for a technical role, Zara might ask coding questions or architectural questions; for a PM role, it might pose behavioral scenarios. The AI can handle clarifications – e.g. if a candidate asks for more detail or context on a question, Zara (powered by GPT-4) can respond in the moment, something earlier scripted chatbots could not do well. After the interview, Zara instantly produces a detailed feedback report assessing the candidate’s strengths and weaknesses (both to help the employer make a decision and, if the candidate requests it, to give them personal feedback). This tackles a long-standing pain point: human interviewers rarely give candidates feedback due to time and legal risk, but the AI can deliver personalized, structured feedback at scale. According to the study, candidates who were not selected could receive an emailed report highlighting areas to improve (e.g. specific technical concepts to brush up) – a novel experience in recruiting.

The results from deploying Zara in a real hiring setting are promising. Over 3 days, Zara conducted 4,820 AI-led interviews for micro1’s recruiting pipeline. Candidate reception was measured by a post-interview survey (Net Promoter Score), where Zara’s interviews averaged 4.37 out of 5 – indicating generally positive candidate satisfaction. Only about 10.7% of candidates requested the optional detailed feedback, but the fact that thousands could instantly get an interview and even get feedback is a significant improvement over being “ghosted” by employers. Interestingly, the researchers also compared the quality of interviews to human-led ones. They found the AI-led interviews were rated as having slightly better question quality and much better conversational flow than human interviews on average. Specifically, human technical interviews got a 7.78/10 score for question quality and a 5.49/10 for conversational dynamics, whereas Zara’s AI interviews scored 8.60 and 8.27 respectively on those metrics. The big jump in conversational dynamic score suggests the AI’s interactive approach (letting candidates ask for clarifications or additional context, and adjusting accordingly) made the interview feel more like a supportive conversation, whereas human interviewers perhaps varied widely in interactivity. Of course, humans often intentionally put candidates on the spot, which might explain lower “conversation feel” scores – so a higher score isn’t necessarily indicating a better hiring outcome. But these metrics show AI can conduct a structured interview that candidates find at least as fair and thorough as a human-conducted one. Zara’s implementation also included a query-handling agent to answer candidates’ questions during the process (e.g. if a candidate asks, “Will I get a copy of this recording?” or “How does this interview affect the hiring decision?”, the AI can respond consistently). The system resolved 75% of candidate inquiries autonomously, further reducing the need for recruiter intervention.

Another system, proposed by Pathak and Pandey (2025), uses a multi-agent AI architecture for recruitment. In their approach, different AI agents handle sourcing, interviewing, evaluation, and decision-making in an end-to-end automated hiring pipeline. Notably, their “Vetting Agent” is a GPT-based interviewer that conducts asynchronous technical interviews (for example, coding challenges or technical Q&A via chat). Then an Evaluation Agent applies a rubric to score the performance and even generates feedback for consistency. Finally, a Decision Agent compiles the results into a recommendation for hiring. In tests with over 500 applicants, this multi-agent system sped up hiring by 65% and achieved 91% agreement with human expert hiring decisions. Candidate satisfaction was high (4.6 out of 5) and, importantly, the study reports that using standardized AI interviews and rubric scoring “effectively diminished the evaluation differences which stemmed from candidate demographics.” In other words, by using the same structured criteria for everyone and removing human prejudices, the AI-driven process yielded more uniform outcomes across genders or other groups – hinting at the potential for reduced bias. This is a critical claim, given fears that AI might perpetuate bias. It suggests that if carefully engineered (and audited), AI interviewers can actually help standardize evaluations and focus on job-relevant answers.
Key Challenges in AI-Conducted Hiring

While the successes are encouraging, AI interviewers in hiring face special challenges. One major concern is bias and fairness. LLMs themselves can have biases in how they phrase questions or evaluate responses. A 2024 study by Kong et al. found evidence of gender bias in LLM-generated interview responses – meaning if the AI is role-playing or generating model answers, it might systematically favor one gender’s communication style unless mitigated. Additionally, if an AI interviewer has been trained on historical data that reflects biased decisions (e.g. more favorable toward a certain background), it could inadvertently carry that forward. To address this, companies like Sapia publish fairness audits and ensure their models exclude certain sensitive factors. New York City and some jurisdictions now mandate AI bias audits for automated hiring tools, pushing developers to prove their systems don’t unduly discriminate. Ensuring the AI’s questions themselves are unbiased and job-related is equally important – an AI must not ask illegal or inappropriate questions (e.g. about age, family, etc.), which requires stringent prompt design and testing.

User trust is another challenge. A portion of candidates remain uncomfortable being evaluated by a machine. They fear the AI may not understand their unique story or might take things out of context. For instance, if a candidate has an unusual career path, a human interviewer might be charmed by their story, whereas an AI might flag it as inconsistent. Transparency can help – some platforms explain to candidates how the AI works and that a human will review AI recommendations. Candidates are also advised to treat AI interviews seriously; showing enthusiasm even when talking to a bot can improve outcomes. As one career coach noted, “Even when it’s just you and your screen, your energy matters” in one-way AI interviews, since monotone or terse responses might be interpreted poorly.

Depth and adaptiveness are somewhat double-edged in AI interviews. On one hand, an LLM can ask decent follow-ups if programmed (Zara clarified questions, and the multi-agent system allowed back-and-forth). On the other hand, AI may struggle with truly creative follow-ups or reading between the lines the way a human might. For example, a human interviewer might sense when a candidate is holding back and change tactics; an AI might naively move to the next question. However, as LLMs get more advanced and are fine-tuned for conversation, this gap is closing. Modern systems already allow candidates to ask clarifying questions, which human interviewees appreciate. Zara’s improvement in conversational scores partly came from allowing candidates to “actively engage and seek clarity throughout the interview”, leading to more precise Q&A exchanges.

Regulatory and legal considerations are also significant. Hiring is subject to anti-discrimination laws, and any automated decisions must be explainable in some contexts (e.g. the EU’s GDPR/right-to-explanation). If an AI unfairly filters out a protected group, employers could face lawsuits. Thus, many firms use AI interviewer outputs as assistive rather than definitive – a human recruiter often reviews the AI’s recommendations before making decisions, as a safeguard. In micro1’s case, “AI-generated assessments are subsequently reviewed by human recruiters” before candidates move to the next round. This human-in-the-loop approach is common, at least until stakeholders have more trust in the AI’s judgment.

Finally, candidate experience must be managed. Not everyone enjoys speaking to a robot. Some Gen Z applicants might actually prefer it (an AI might feel less intimidating than a human interviewer), while others, like those cited in an NBC report, found it “super uncomfortable” to interview with no human feedback or felt an AI interview was only a hurdle to get past before talking to a real person. Companies are trying to make the AI interactions more engaging – e.g. using an empathetic tone, providing at least some feedback or reactions (some avatars will nod or say “thank you” after an answer to simulate human conversational cues). There is also an emerging practice of prepping candidates for AI interviews, so they know what to expect and don’t panic at the lack of immediate human response. For instance, advice columns suggest practicing answers with an AI coach, ensuring your responses are picked up correctly by speech-to-text (for video bots), and maintaining a positive tone (since the AI might be “listening” for positive vs negative framing).
Key Technical Challenges and Considerations

Across both user research and job interview applications, several technical and ethical challenges shape the development of autonomous LLM interviewers:

    Naturalness and User Trust: For an interview to be effective, the interviewee must feel comfortable and trust the interviewer (human or AI). AI agents need to establish a degree of rapport. This involves using a friendly and adaptive tone, acknowledging responses appropriately, and not seeming too robotic. LLMs can produce fluent and even empathetic language, but careful prompt engineering is needed to avoid repetitive or insincere-sounding responses. Some user research bots explicitly include small talk or empathy prompts (e.g. “Thank you for sharing that, I understand that must be frustrating”) to put users at ease. Even so, certain populations might be less inclined to open up to AI. The Greylock report observed that overall participants tended to open up more to AI, but this may vary by individual. Building trust also means being transparent that the agent is an AI (to avoid deception) and ensuring data privacy. Both research and hiring interviews can involve sensitive information, so the underlying systems must securely handle and store transcripts.

    Bias and Fairness: As noted, bias is a serious concern. An AI interviewer must be tested for biased behavior – e.g., does it ask different questions or conduct shorter interviews for different demographics? Does the sentiment analysis or scoring inadvertently favor a particular speech style or dialect (which might correlate with ethnicity or gender)? There is ongoing research into debiasing LLMs and auditing their outputs. In recruitment, frameworks like the FAIR Hiring standard are applied, and companies publish validation studies. In user research, bias might manifest in how the AI interprets feedback (for instance, if analyzing sentiment, it should not misclassify emotional tone differently for different groups). Mitigations include fine-tuning models on diverse data, using rule-based constraints for certain sensitive questions, and keeping a human review loop for initial deployments.

    Adaptability and Context Management: Good interviewers listen and pivot based on the conversation. LLM agents must manage conversation context over multiple turns. With long interviews, context window limits of models can be a problem (though models like Claude offer very large context windows now). Techniques like summarizing earlier parts of the conversation or using retrieval (as CLUE and Zara did for analyzing and referencing past user input) help maintain coherence. There’s also a challenge in ensuring the AI stays on topic. Tangents need to be balanced: in user interviews, sometimes off-topic stories yield valuable insight, but an AI might not know when to deviate from the script versus when to follow the outline. A combination of structured prompts (to ensure coverage of key questions) and open-ended flexibility is ideal. Some implementations, like CLUE-Interviewer, explicitly provided the LLM a list of target dimensions to cover and encouragement to follow up on anything interesting. This guided prompting is critical to get high-quality output – left naïvely to its own, an LLM might either ramble or, conversely, cut the interview short with minimal questions.

    Depth vs. Efficiency: Current LLM agents can simulate semi-structured interviews quite well, but truly unstructured, exploratory ethnographic interviews remain challenging. Humans excel at intuitively sensing when to probe deeper into an emotional story or how to phrase a difficult question tactfully. AI can be hit-or-miss on these fronts. For example, showing empathy: a model might have learned to say “I’m sorry to hear that” in response to any negative sentiment, but using it inappropriately (or too often) could seem fake. Ensuring conversation depth also means training the AI to ask the “why” questions. If a participant says they dislike a product feature, will the AI just note it or will it ask “Why do you feel that way?” or “What would you prefer instead?” The best systems explicitly instruct the AI to seek clarifications and reasons until the point of diminishing returns. However, too many follow-ups can exhaust participants. Tuning this balance is something human interviewers learn with experience; AI rules may need refinement through trial and error.

    Voice and Embodiment: For voice-based agents, there are additional technical hurdles. Speech recognition errors can distort a participant’s answer and lead the AI off-track (imagine an AI interviewer mishearing a crucial word and then asking an irrelevant follow-up). High-accuracy ASR models are needed, especially for diverse accents. Text-to-speech for the AI’s voice should be pleasant and ideally expressive; a monotone synthetic voice could make the interviewee disengage. Some companies use friendly avatars or even physical robots (like the Swedish robot Tengai which was designed to nod and smile in a neutral way) to give a human-like presence. Tengai was an early example of an embodied AI interviewer aimed at eliminating bias – it asked all candidates identical questions in the same tone, attempting to standardize the interview process. While Tengai’s original programming was simpler, modern LLM integration could make such robots much more conversational. Still, avatars and robots introduce UI/UX considerations: eye contact, facial expressions, etc., must be well-calibrated to avoid the “uncanny valley” or unintended cues.

    Data and Training: High-quality AI interviews require not just an LLM, but often domain-specific tuning. For user research, if you want the AI to interview about a mobile app, you may need to provide it context about the app or typical issues to probe. Some platforms allow researchers to feed a project brief or objectives which the AI uses to generate relevant questions. In recruiting, tailoring to a job role is crucial – e.g., for a sales job the AI should ask about hitting targets, for engineering it might pose a technical challenge. This is where the combination of LLM with structured frameworks comes in. Sapia’s “Jas” tool, for instance, builds a competency model from the job description and then generates interview questions weighted to those competencies. The flexibility of LLMs to generate custom questions on the fly is very useful; however, ensuring the questions are valid and non-discriminatory often requires a human-in-the-loop or a library of vetted questions. Some systems use hybrid approaches: e.g., an LLM suggests questions but only chooses from a pre-approved pool or gets human review for new questions, at least during development.

    Analysis and Interpretation: After conducting interviews, AI agents often double as analysts – transcribing and summarizing the data. While LLMs are quite good at summarizing text, there’s a risk of hallucinations or misinterpretation. If a participant’s answer is nuanced, the AI might oversimplify it in the summary. Researchers still need to validate AI-generated insights. In CLUE’s case, they built a separate Insighter module to categorize responses and extract topics, and found it was “sufficient to provide a bird’s-eye view” of user opinions, though not perfect. Likewise, recruitment agents scoring answers must be calibrated to human judgments. That 91% human-agreement figure in Pathak & Pandey’s study implies 9% of candidates got different AI vs human evaluations, which could be problematic if not caught. Ensuring interpretability of AI judgments is key so that when there’s a discrepancy, humans can understand and override AI decisions if needed.

Despite these challenges, the capabilities of LLM interview agents have rapidly advanced. Today’s AI interviewers can handle multi-turn, context-rich dialogues, ask intelligent follow-ups, and even exhibit basic empathy or humor. They deliver consistency (every user or candidate is treated to the same quality of questions) and scale (hundreds of interviews can happen in parallel, anytime). For organizations, this opens up possibilities like continuous user discovery – e.g., an AI could routinely interview users after each app feature release to gather instant feedback – or wider candidate outreach – e.g., screening thousands of applicants in a fair, standardized way rather than relying on resumés alone.
Comparing AI-Led vs Human-Led Interviews

It’s important to understand where AI interviewers excel and where they fall short compared to humans:

    Consistency and Objectivity: AI interviewers ask each person the same core questions in the same manner, which can reduce human inconsistencies or biases. For user research, this means data might be more uniform for analysis (less variation due to different interview styles). For hiring, this can improve fairness – every candidate gets an equal opportunity to present themselves on the same questions. Humans, however, might unconsciously lead an interviewee or skip questions, introducing variance. On the flip side, a great human interviewer knows when the script should be bent (e.g., dropping a question that’s not applicable to a particular interviewee), whereas an AI might rigidly ask it unless programmed to recognize the situation.

    Engagement and Empathy: Human interviewers build rapport through eye contact, listening noises (“mm-hmm”), and adaptive empathy. AI is catching up – for instance, LLM agents can be prompted to respond empathetically to negative statements – but it can come across as scripted. In sensitive interviews (e.g., a user describing a personal frustration, or a candidate explaining a career gap due to family reasons), a human’s ability to convey genuine understanding can encourage the interviewee to open up more. That said, some interviewees prefer the non-judgmental neutrality of AI. Especially in job interviews, candidates who fear discrimination might feel more comfortable that an AI won’t judge their appearance or accent. There is anecdotal evidence of candidates with autism, for example, finding AI interviews less stressful since they don’t have to interpret the interviewer’s social cues or worry about theirs. Thus, AI interviews might actually level the playing field for some by removing the “chemistry” factor that can bias human hiring.

    Depth of Insight: Well-trained LLM interviewers have shown they can uncover insights comparable to human-led sessions. In user research, AI can recall everything said (thanks to transcripts) and won’t forget to ask an important question. But humans can sometimes spontaneously ask creative questions that a scripted AI wouldn’t know to ask. For instance, if a user mentions something completely unexpected, a human might follow that tangent and discover a breakthrough insight; an AI might not recognize the opportunity without human guidance. Some teams address this by allowing researchers to monitor live AI interviews and “whisper” a question to the AI to ask if they see fit – effectively a human-AI partnership. In hiring, humans are better at reading non-verbal cues in real time (though as noted, AI can analyze some cues in video interviews). Humans may also detect authenticity or bluffing through intuition, whereas current AI mainly focuses on the content of answers. However, AI could be less prone to being “charmed” by surface personality; it sticks to the rubric.

    Scalability and Cost: There’s no doubt AI wins on scalability. An AI interviewer can conduct 20 interviews simultaneously, 24/7, without fatigue, whereas a human interviewer is one-to-one and limited by working hours. This drastically lowers the marginal cost per interview. Greylock’s analysis highlighted that AI-native research can lead to dramatically “faster time-to-insight” and much higher frequency of research because calendars and headcount are no longer bottlenecks. For startups or small teams (whether product teams or HR teams), an AI interviewer can substitute for adding multiple staff – one product manager noted they could scale from a dozen interviews a week to 20+ by using an AI interviewer as a force-multiplier. That being said, AI platforms do come with their own costs (subscription fees, etc.), but generally a fraction of the cost of equivalent human hours.

    Reliability and Quality Control: Human interviewers sometimes make mistakes (skipping a question, misphrasing something) but they won’t crash or glitch. An AI interviewer, being software, can suffer from technical issues – a mis-heard word, a server error, or a weird LLM hallucination where it asks an irrelevant or confusing question. Such instances can undermine the interview. Rigorous testing and guardrails are put in place to minimize this, and transcripts can be reviewed to catch any AI missteps. In critical interviews (say, a CEO interview for a key hire), no one is likely to rely on AI alone at this stage – human involvement would be expected for important decisions or research insights that have major business impact.

In summary, current capabilities of LLM-based interview agents are already impressive: they can reliably conduct structured interviews, follow up intelligently, handle both text and voice interaction, and produce useful summaries or scores. They shine in scalability, consistency, and speed of analysis. Limitations persist in emotional intelligence, truly open-ended exploration, and user trust – areas where humans still have an edge. The choice between AI vs human (or how to mix them) often comes down to context. For exploratory, early-stage user research where breadth is needed, an AI can churn through many interviews to identify patterns, which a human team can then explore in depth. For high-stakes or very nuanced conversations (e.g. a design thinking interview with a key customer, or an executive job candidate interview), humans are likely to remain in the loop for the foreseeable future. Indeed, the consensus in both domains is that AI won’t replace human experts, but will augment them. By taking over the repetitive and large-scale tasks, AI frees up humans to focus on strategy, empathy, and creative thinking – the parts of interviews that truly require a human touch.
Conclusion and Future Outlook

The emergence of autonomous LLM interviewers is reshaping how organizations gather information from people. In user research and product discovery, AI agents are enabling continuous user insight at a scale and speed previously unattainable – bringing qualitative feedback into agile product loops. In recruitment, AI interviewers are streamlining the hiring funnel, making it more efficient and potentially more fair, while also offering candidates quicker feedback and engaging experiences (when done right). Major tech players and research labs are investing in this space: Anthropic’s and Stanford’s large-scale AI interviews demonstrate the research community’s interest, and startups like Sapia, Outset, and others are shaping the commercial landscape with innovative solutions.

Going forward, we can expect further improvements in these AI agents’ adaptiveness and emotional intelligence. As multimodal LLMs develop, an interview agent might simultaneously analyze a person’s tone of voice and facial expression to adjust its approach – for instance, noticing if a candidate seems nervous and offering a gentle prompt to put them at ease. We may also see specialized interview agents fine-tuned for particular domains: e.g., an AI interviewer that is an expert in medical research interviews (knowing how to ask about health behaviors sensitively), or one for technical coding interviews that can ask coding questions and even check code in real-time.

Another area of growth is integrating these agents more deeply into workflows. In user research, AI interviews will feed directly into product management tools – imagine AI-run interviews whose insights auto-populate a dashboard of user needs, or even create user personas on the fly. In hiring, AI interviews might link with on-the-job assessments – for instance, an AI that interviews a candidate and then automatically administers a skills test or pair-programming exercise, acting as both interviewer and proctor.

Challenges such as bias mitigation and candidate/user acceptance will remain top priorities. We will likely see stricter guidelines and possibly regulations ensuring AI interviews are fair and transparent (especially in employment). Companies deploying these systems at scale will need to be vigilant in monitoring outcomes and maintaining a human oversight channel.

In conclusion, autonomous LLM interview agents have progressed from experimental demos to real-world applications that are capturing valuable interviews and insights at scale. They represent a convergence of conversational AI and domain-specific knowledge (whether UX or HR). While not a wholesale replacement for human judgment, these agents are rapidly becoming powerful “co-interviewers” – handling the routine and scaling aspects of interviews, and working alongside humans who provide direction and interpretation. As one practitioner put it, “because of AI, we’re moving into roles which allow us to focus on higher-impact decisions”, with the AI taking care of the heavy lifting. The major developments highlighted – from academic prototypes like CLUE and Zara to commercial platforms like Listen, Strella, and Sapia – are paving the way for a future where conducting an interview with an AI is as normal as sending a survey. The focus now is on refining these agents to be more trustworthy, adaptive, and human-aware, so that they can truly autonomously conduct interviews that are as effective as those done by skilled humans, if not more.

Sources:

    Liu, Mengqiao, et al. “Understand User Opinions of LLMs via LLM-Powered In-the-Moment UX Interviews.” arXiv preprint 2502.15226 (2025).

    Maze (Jo Widawski). “User research with humans vs. AI: Which is better?” Maze Blog (2025).

    Saran, Jo & Saif, Sarah. “The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight.” Greylock Partners Blog (June 2025).

    Listen Labs – Product Page (2025).

    Outset.ai – Platform Page (2025).

    Strella – Product Page (2024).

    Convo (getconvo.ai) – Product Page (2025).

    Reforge Research – “AI User Interviewer” (2025).

    NBC Academy (E. Lee). “How to Nail Your Job Interview with an AI Chatbot.” (Oct 2025).

    Yazdani, Nima, et al. “Zara: An LLM-based Candidate Interview Feedback System.” arXiv preprint 2507.02869 (2025).

    Pathak, Gangesh & Pandey, Divya. “AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring.” SSRN (May 2025).

    Sapia.ai – AI Interview Platform page (2025).

    Anthropic. “Introducing Anthropic Interviewer: What 1,250 professionals told us about working with AI.” Anthropic Research Blog (Dec 2025).

    Beltoft, S.L. et al. “Interview Bot: Can Agentic LLMs Perform Ethnographic Interviews?” Proc. ICAART 2025.

Citations

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Introducing Anthropic Interviewer \ Anthropic
https://www.anthropic.com/research/anthropic-interviewer

Introducing Anthropic Interviewer \ Anthropic
https://www.anthropic.com/research/anthropic-interviewer

AI Agents Simulate 1,052 Individuals’ Personalities with Impressive Accuracy | Stanford HAI
https://hai.stanford.edu/news/ai-agents-simulate-1052-individuals-personalities-with-impressive-accuracy

AI Agents Simulate 1,052 Individuals’ Personalities with Impressive Accuracy | Stanford HAI
https://hai.stanford.edu/news/ai-agents-simulate-1052-individuals-personalities-with-impressive-accuracy

https://www.scitepress.org/publishedPapers/2025/133878/pdf/index.html

https://www.scitepress.org/publishedPapers/2025/133878/pdf/index.html

https://www.scitepress.org/publishedPapers/2025/133878/pdf/index.html

https://www.scitepress.org/publishedPapers/2025/133878/pdf/index.html

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Introducing Anthropic Interviewer \ Anthropic
https://www.anthropic.com/research/anthropic-interviewer

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

Listen Labs | AI-led User Interviews
https://listenlabs.ai/

The AI-Moderated Research Platform | Outset
https://outset.ai/

The AI-Moderated Research Platform | Outset
https://outset.ai/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Strella – the AI-powered Customer Research Platform
https://www.strella.io/

Conveo | Confident decisions in days with AI-led interviews.
https://conveo.ai/

Conveo | Confident decisions in days with AI-led interviews.
https://conveo.ai/

User Interview Software | AI-Powered Qualitative Research Platform - Convo
https://getconvo.ai/

User Interview Software | AI-Powered Qualitative Research Platform - Convo
https://getconvo.ai/

User research with humans vs. AI: Which is better? | Maze
https://maze.co/collections/ai/humans-vs-ai-user-research/

User research with humans vs. AI: Which is better? | Maze
https://maze.co/collections/ai/humans-vs-ai-user-research/

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

Reforge Research | AI User Interviewer
https://www.reforge.com/research/interviewer

Reforge Research | AI User Interviewer
https://www.reforge.com/research/interviewer

Reforge Research | AI User Interviewer
https://www.reforge.com/research/interviewer

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Conversational hiring software that gets work done for you — Paradox
https://www.paradox.ai/

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

How to Nail Your Job Interview with an AI Chatbot
https://nbcuacademy.com/ai-interview-chatbot/

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Zara: An LLM-based Candidate Interview Feedback System
https://arxiv.org/html/2507.02869v1

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

Robot interviewers: How recruitment is evolving for Gen Z ...
https://www.worklife.news/technology/robot-interviewers-how-recruitment-is-evolving-for-gen-z-professionals/

Robots Could Be Conducting Job Interviews Next Year - YouTube
https://www.youtube.com/watch?v=c8rfWRdvv00

Conveo | Confident decisions in days with AI-led interviews.
https://conveo.ai/

Conveo | Confident decisions in days with AI-led interviews.
https://conveo.ai/

Sapia.ai | AI Interview Platform
https://sapia.ai/

Understand User Opinions of Large Language Models via LLM-Powered In-the-Moment User Experience Interviews
https://arxiv.org/html/2502.15226v1

AI Agents in Recruitment: A Multi-Agent System for Interview, Evaluation, and Candidate Scoring by Gangesh Pathak, Divya Pandey :: SSRN
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5242372

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

The Rise of AI-Native User Research: From Scheduled Interviews to On-Demand Insight | Greylock
https://greylock.com/greymatter/ai-user-research/

User research with humans vs. AI: Which is better? | Maze
https://maze.co/collections/ai/humans-vs-ai-user-research/

Introducing Anthropic Interviewer \ Anthropic
https://www.anthropic.com/research/anthropic-interviewer
All Sources
greylock
arxiv
anthropic
hai.stanford
scitepress
listenlabs
outset
strella
conveo
getconvo
maze
