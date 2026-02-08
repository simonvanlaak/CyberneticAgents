# The biggest problem with Agentic Products - Onboarding

What were the things that really frustrated you when using ChatGPT, Claude, Mistral, etc.? What made you stop using them?

I often hear from people how great the opportunities are and that I should be using agentic products more, incorporate them into my work. We see so many companies adding "AI" and some stardust emoji to their websites. But often there are attempts of using this technology, just cramming it into an existing product without much benefit for the user. Many companies just don't understand how this new technology can be helpful, what value it could add to the existing product.
And I feel the same is the case for myself, I hear all this talk about using "AI" for everything, but don't know what I should use it for or where it could be helpful for myself. I end up trying out a lot of different products, but rarely find that they create significant value for myself.
That I think is the biggest problem with current agentic products, they can do everything (or at least claim that) but in the end it's either just not good enough or because you could do anything you end up using them for nothing.
I briefly mentioned this already in the last post but want to dive deeper into this here.

I think on-boarding is key, in every product but especially in agent products. They main challenge during on-boarding in agent tools is this, they need a lot of context, a lot of information about the user, what they are working on, what tools they are using in order to be able to provide good answers or suggestions. Manually providing this context via chat messages takes a lot of effort, explaining what my job is, what I study or where I live. But if I don't put in this effort, every answer is generic and the chat bot just doesn't provide any value for me. I notice this especially when I try out a new provider / platform and start with a blank slate.

The question is how can the agent get relevant context, with low user effort?

## The Solution
Here is the solution I came up with so far:
1. Get what's already written down
2. Ask follow up questions
3. Suggest value creation

### 1. Get what's already written down
The best way for agents to consume context is in written from. 
During my live in the digital word I wrote a lot of things down. Be it in chat messages with friends, in google docs at work, or when taking notes on my phone. I'm constantly writing things down.
This collection of information is worth gold to the agent. Just the simple act or reading my public linkedin page would provide a great deal of context without much effort from my side, all I have to do is copy-paste the link.
The on-boarding and getting started with a new agent can be significantly less work, if the agent can scan though all the things I have already written down and use that to get an understanding on who I am and what my goals are.
This really goes to a next level if the agent is provided with access to personal documents, for example Notion / Obsidian / One Note. This data can be searched and analyzed on a first run, but also accessed ad-hoc if more context is needed for specific conversations.

### 2. Ask follow up questions
I don't write down the things that are most obvious for me. There is just no need for that, because they are so present in my memory. But these are key points of information for the agent. So we need follow up questions. Equipped with all the existing knowledge, they don't end up being vague and broad like what my favorite color is or a question I hate that these agentic products ask a lot, "do you prefer a friendly or professional style in my answers?"
Instead because the context is already available the questions can be very specific, asking which of the ongoing projects is more important right now, getting key information on people mentioned in notes and so forth.
The main goal of these follow up questions is (similar to in a product discovery interview), first understand what are the users needs, what problems am I currently dealing with and which ones create the biggest pain.

### 3. Suggest value creation
Having understood the users pain, now comes the value creation part. With a good understand of what agents are capable, what tools are/could be available and also where agents might have weaknesses, ideas can be created of how agents could ease the users problems. This could be small automation all the way to taking over marketing. Mainly depending on the agents limits.
But if the agents themselves can come up with ideas and solutions that actually fit the users need, they can create value. And propose tasks that can be delegated to them. This would close the main issue of staring at the blank screen and instead create a smooth user experience that quickly delivers value.


## How I'm trying to implement this
The on-boarding starts with a technical setup, where the user connects a telegram chat bot, provides credentials to their Notion or Obsidian Knowledge Management and is also asked to paste a few public links (such as linked in or own website). 

Then the interview starts. It begins with a fairly open ended questions that comes as a default. The users replies to the question via a voice note on telegram. The big benefit of voice notes is that they encourage the person to give a lot of information and think for a bit because the effort to speak is much lower than to type out the answers. 

While the user is answering the question, the agents are working at full speed in the background. They are reading through the provided documents, doing web-searches and synthesizing the data into clear information on the user. They write this information into a memory database that can be quickly accessed on demand by the agents.

Now the voice note gets transcribed and information gained there gets added to the existing memory. The followup question that is being asked next now builds on all the already synthesized information, creating an engaging interview experience for the user.

This interview could last for 10-15 minutes, in which the agents start suggesting potential automations / projects they could get started with to help the user.
