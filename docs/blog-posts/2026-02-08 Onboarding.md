# The biggest problem with Agentic Products - Onboarding

What were the things that really frustrated you when using ChatGPT, Claude, Mistral, etc.? What made you stop using them?

The biggest problem with current agentic products is onboarding. Most of them can do almost anything (or at least claim that), but because the product doesn't help you find the *right* thing, you end up doing nothing with it. I experience this myself: I try a lot of tools, but rarely find that they create meaningful value for me.

We see so many companies adding "AI" and some stardust emoji to their websites. Often it's just technology crammed into an existing product without a clear user benefit. Even when the tech is capable, the experience still fails at the start. That is why onboarding is the key challenge for agentic products.

The core issue is context. Agent tools need a lot of information about the user, what they are working on, and which tools they use before they can provide good answers or suggestions. Manually providing this via chat is high effort: explaining my job, my goals, my current projects, and my workflow. If I skip that, every answer is generic and the chatbot provides no real value. I feel this most when I try a new provider or platform and start with a blank slate.

So the question becomes: how can an agent get relevant context with low user effort?

## The Solution
Here is the solution I have come up with so far:
1. Get what's already written down
2. Ask follow-up questions
3. Suggest value creation

### 1. Get what's already written down
The best way for agents to consume context is in written form.
During my life in the digital world I write a lot of things down. Be it chat messages with friends, Google Docs at work, or notes on my phone. I'm constantly writing things down.
This collection of information is worth gold to the agent. Just the simple act of reading my public LinkedIn page would provide a great deal of context without much effort from my side, all I have to do is copy-paste the link.
Onboarding can be significantly less work if the agent can scan through the things I have already written and use that to understand who I am and what my goals are.
This goes to the next level if the agent has access to personal documents, for example Notion, Obsidian, or OneNote. This data can be searched and analyzed on a first run, and accessed ad-hoc if more context is needed for specific conversations.

### 2. Ask follow-up questions
I don't write down the things that are most obvious for me. There is just no need for that, because they are so present in my memory. But these are key points of information for the agent. So we need follow-up questions. Equipped with all the existing knowledge, they don't end up being vague and broad like what my favorite color is or a question that these agentic products ask a lot, "do you prefer a friendly or professional style in my answers?"
Instead, because the context is already available, the questions can be very specific. It could ask which of the ongoing projects is more important right now, getting key information on people mentioned in notes and so forth.
The main goal of these follow-up questions is similar to a product discovery interview: first understand the users' needs, what problems I am currently dealing with, and which ones create the biggest pain.

### 3. Suggest value creation
Having understood the users' pain, now comes the value creation part. With a good understanding of what agents are capable of, what tools are or could be available, and where agents have weaknesses, they can generate ideas for how the system could ease the users' problems. This could be small automations all the way to taking over marketing, depending on the agent's limits.
If the agent can propose ideas and solutions that actually fit the users' needs, it creates real value. It also closes the main issue of staring at a blank screen and instead creates a smooth experience that quickly delivers results.

## How I'm implementing this in the Cybernetic Agents Project
The onboarding starts with a technical setup. The user connects a Telegram chatbot, provides credentials to their Notion or Obsidian knowledge management system, and pastes a few public links (such as LinkedIn or their own website).

Then the interview starts. It begins with a fairly open-ended question. The user replies via a voice note on Telegram. The big benefit of voice notes is that they encourage the person to give more information and think for a bit because speaking is much lower effort than typing.

While the user is answering, the agents work in the background. They read through the provided documents, do web searches, and synthesize the data into clear information on the user. They write this information into a memory database that can be accessed quickly by the agents on demand.

Now the voice note gets transcribed, and the information gained there is added to the existing memory. The follow-up question builds on all the synthesized information, creating an engaging interview experience for the user.

This interview could last for 10-15 minutes, in which the agents start suggesting potential automations or projects they could get started with to help the user.

# What next?

Thanks for reading this far, I’m just at the beginning of this project and still figuring out where it’s going. You can help me by asking questions about the parts that don’t make sense. It forces me to get more precise and improve the project!

If I got you excited, check out the open source project on GitHub.

I'm looking for people who would like to do an interview with me to help me improve the project. If you're interested, please reach out to me on LinkedIn or via email.

Thanks,
Simon

First posted on https://simonvanlaak.de
