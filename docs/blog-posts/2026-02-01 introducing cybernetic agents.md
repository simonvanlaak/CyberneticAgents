# Introducing CyberneticAgents, the reason why I quit my job

This project feels huge, and for a while I didn’t know where to start. A lot brought me here: 4.5 years ago I started at IMAGO and began studying at CODE in the same month. Along the way I became obsessed with Salvador Allende and Chile’s attempt to redesign economic coordination in the early 1970s. That curiosity pulled me into cybernetics, Stafford Beer, and eventually to today’s multi‑agent LLM (large language model) systems.

# What happened in Chile?

Starting with Allende, here’s a quick (and probably oversimplified) introduction. When the government nationalized large parts of Chile’s economy, it faced the challenge of managing many newly acquired businesses without their previous owners and managers. The idea was to enable worker‑led self‑organization, and to coordinate across enterprises without a massive central bureaucracy.

A group of young economists linked this challenge to cybernetics, the science of control and communication in complex systems. They believed it could help design an organizational structure where businesses could manage themselves, communicate with each other, and escalate critical issues to the government. This effort became known as Project Cybersyn. They invited Stafford Beer, a cybernetics researcher and business consultant, who applied his methods and helped build the system. The project was cut short after the 1973 military coup (supported by the CIA), and Beer later synthesized what he learned into the "Viable System Model".

If this sparked your interest, have a look the references at the end of the post.

# What does that have to do with LLMs?

Here’s a classic cybernetics line that stuck with me: “It is not necessary to enter the black box to understand the nature of the function it performs.” We don’t truly understand what happens inside an LLM, it is a black box. Cybernetics is exactly about that, steering outcomes without having to understand the inner workings of the systems that are being steered.

Think of a thermostat. You set a target temperature, and a thermometer compares the room temperature to the target. If it’s too cold, the system turns on heating. That’s called a feedback loop, a key part of steering in cybernetics.

When a chatbot misunderstands you and runs down the wrong rabbit hole, when multiple agents are stuck in a loopand waste tokens, or when they fail to collaborate effectively, you’re dealing with a cybernetic (steering) problem. I’m arguing that many of the hard problems in LLM systems are cybernetic in nature: we’re trying to steer autonomous systems whose internals are opaque to us.

# Wait, you quit your job?

I started thinking about cybernetics and llm agents about a month ago, while I was still planning to write my bachelor thesis on a different topic. Then, less than 24 hours before a vacation in Italy, I quit my job to focus on this instead.

I joined IMAGO at the same time I started at CODE University and had planned to write my thesis there. Business priorities changed and my project was canceled, so I needed a new thesis topic. I decided to dive deep into applying cybernetic principles to multi‑agent systems, hoping to find a thesis in the process. I was coding until 5am, telling myself it was time to sleep. Token limits were the only reason I did the dishes.

# So what are you actually building?

The Viable System Model is a structure for how autonomous systems cooperate to achieve a shared goal while adapting to their environment. It’s a strong base for multi‑agent systems because it embeds many cybernetic principles and gives a clear organizational skeleton.

I’ll go into details in another post, but one key idea matters here: the goal of a viable system is to stay viable. You’ve probably tried a bunch of LLM tools and abandoned many of them. Why? Most fail to help you understand what they’re good for. Instead, there’s just a blank input field and a blinking cursor, and few things are scarier than a blank page. I often deleted tools because I had no idea how to use them. These tools aren’t viable: they can’t sustain themselves. They cost more than the value they create, because we don't know what value they could create for us.

The primary focus of CyberneticAgents is to understand what creates value for the user, compare that to the costs it creates, and stay net positive. In short: stay viable.

“Hey, I noticed you’ve asked me five times to summarize an email. How about I send you a summary of new emails every morning? Based on your current volume, that would cost about 38 cent per day.”

# What next?

Thanks for reading this far, I’m just at the beginning of this project and still figuring out where it’s going. You can help me by asking questions about the parts that don’t make sense. It forces me to get more precise and improve the project!

If I’ve sparked your interest, here are a few paths to read more:
- [Salvador Allende’s presidency](https://en.wikipedia.org/wiki/Presidency_of_Salvador_Allende)
- [Project Cybersyn](https://en.wikipedia.org/wiki/Project_Cybersyn) & [German radio feature (where I learned about this in the first place)](https://www.hoerspielundfeature.de/chiles-kybernetischer-traum-von-gerechtigkeit-projekt-104.html)
- [Cybernetics](https://en.wikipedia.org/wiki/Cybernetics) & the [Viable System Model](https://en.wikipedia.org/wiki/Viable_system_model)
- [Multi‑agent systems](https://www.anthropic.com/engineering/multi-agent-research-system)

If I got you excited, check out the open source project on GitHub.
I know others have had similar ideas, so please reach out if you want to collaborate. I’ll clean it up a bit for us.

Simon

First posted on https://simonvanlaak.de

Title image by Rana from Wikipedia: https://commons.wikimedia.org/wiki/File:CyberSyn-render-005.png

Other things I mentioned:
- https://openclaw.ai/
- https://www.imago-images.com/
- https://code.berlin/
- https://en.wikipedia.org/wiki/Stafford_Beer
