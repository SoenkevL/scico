---
apply: by model decision
instructions: whenever tasked with writing code or understanding it or when working with python or python files
---

## 🐍 Python

Python is the main language our projects are written in. It is a  
very accessible, easy to learn language. Of course, it comes with its own disadvantages. Its not the fastest and small  
errors can happen that are only errors in the human mind but not in the mind of the machine. Great freedom comes with  
great responsibility. Therefore we would like to establish some guidelines here.

### 📜 The Zen of Python

There is a small list of aphorisms by Tim Peters which lay the basis for all to come.

```  
Beautiful is better than ugly.  
Explicit is better than implicit.  
Simple is better than complex.  
Complex is better than complicated.  
Flat is better than nested.  
Sparse is better than dense.  
Readability counts.  
Special cases aren't special enough to break the rules.  
Although practicality beats purity.  
Errors should never pass silently.  
Unless explicitly silenced.  
In the face of ambiguity, refuse the temptation to guess.  
There should be one-- and preferably only one --obvious way to do it.  
Although that way may not be obvious at first unless you're Dutch.  
Now is better than never.  
Although never is often better than *right* now.  
If the implementation is hard to explain, it's a bad idea.  
If the implementation is easy to explain, it may be a good idea.  
Namespaces are one honking great idea -- let's do more of those!  
```  

### 🧰 Some practical tips

To follow the above tips, here are some practical guidelines one can follow:

- Keep nestings minimal, if you go beyond 3 indents maybe its time for another function or a different logic
- Use early returns
- Annotate the types of your variables
- Annotate the return type of your functions
- use descriptive function and variable names
- for longer functions provide a short docstring of what is tranformed into what during execution
- dataclasses, TypedDicts and pydantic BaseModels are great ways to transfer data in code
- using .get on dictionaries allows us to work with default values instead of errors
- using the logger for all errors, warning, info and debugging outputs

## Document structure

Python documents should follow a clear structure

```python
"""short file description (max 2 sentences)"""
# === import global packages ===
from pydantic import BaseModel, ConfigDict
from typing import TypedDict,

...
import logging
from dotenv import load_dotenv
import os
import

...

# === import local file dependencies
from src. import

...

# === initialize global objects ===
load_dotenv()
logger = logging.getLogger(__name__)


# === define classes ===
class example(BaseModel):


class AgentConfig(TypedDict):


# === define protected functions ===
def _example_function(arg1: str, arg2: int) -> str:
    """example function description"""


# === define public functions ===
def example_func(arg1: str, arg2: int) -> str:
    """ example function description"""


# === main functionallity ===
if __name__ == __main__:

```

here add the required classes, objects, functions as is needed. This only serves as an example of how the structure
should look.

Code is always provided embedded within a markdown: providing context and explanations about it.