# mkpy
Makefiles but less archaic

## Comparing the syntax with GNU-Make
`mkpy` is just plain python and regex - intellisense just works!! No need to google obscure make syntax or magic variables.

<table>
<tr>
<th>GNU-Make: Makefile</th>
<th>mkpy: makefile.py</th>
</tr>
<tr>
<td>
  
```makefile
CXX ?= g++
OUTPUT_PLUGIN ?= SDL
IS_DEBUG ?= 0

EXEC := a.out
BUILD_DIR := build
SRC_DIR := src
INC_DIR := include

CFLAGS := -std=c++20 -std=c++20 -Wpedantic -Wall -Wextra 
ifeq ($(IS_DEBUG), 1)
	CFLAGS += -DDEBUG -Wall -fsanitize=address,undefined -g -Og
else
	CFLAGS += -O3
endif

ifeq ($(OUTPUT), SDL)
	CFLAGS += -w -lSDL2main -lSDL2
endif

INC_FLAGS := $(addprefix -I, $(INC_DIR))
INC_DEPS := $(wildcard $(INC_DIR)/*.hpp) $(wildcard $(INC_DIR)/*/*.hpp)

SRCS := $(wildcard $(SRC_DIR)/*.cpp) $(wildcard $(SRC_DIR)/io/*.cpp) $(wildcard $(SRC_DIR)/io/$(OUTPUT)/*.cpp)
OBJS := $(SRCS:$(SRC_DIR)/%.cpp=$(BUILD_DIR)/%.o)

default: $(EXEC)

$(EXEC): $(OBJS)
	$(CC) -o $@ $^ $(CFLAGS)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp $(INC_DEPS)
	mkdir -p $(@D)
	$(CC) $(CFLAGS) -o $@ -c $< $(INC_FLAGS)

clean:
	rm -r $(BUILD_DIR)

```
  
</td>
<td>

```python
from mkpy import target_output, target_phony, sh, format_list_with_regex

import os
from glob import glob
from pathlib import Path

cxx = os.environ.get("CXX", default="g++")
output_plugin = os.environ.get("OUTPUT", default="SDL")
is_debug_build = os.environ.get("DEBUG", default="0")

executable = "a.out"
build_dir = "build"
src_dir = "src"
include_dir = "include"

cxxflags = ["-std=c++20", "-Wpedantic", "-Wall", "-Wextra"]
if is_debug_build == "1":
    cxxflags.extend(["-DDEBUG", "-Wall", "-fsanitize=address,undefined", "-g" "-Og"])
else:
    cxxflags.extend(["-O3"])

if output_plugin == "SDL":
    cxxflags.extend(["-lSDL2main", "-lSDL2"])

include_flags = [f"-I{include_dir}"]
include_deps = glob.glob(f"{include_dir}/**/*.hpp", recursive=True)

src_files = glob(f"{src_dir}/*.cpp") + glob(f"{src_dir}/io/*.cpp") + glob(f"{src_dir}/io/{output_plugin}/*.cpp")
obj_files = format_list_with_regex(f"{src_dir}/(.+)\.cpp", f"{build_dir}/{{0}}.o", src_files)

target_phony("default", [executable])()

@target_output(executable, obj_files)
def link(target, requirements):
    sh(f"{cxx} {' '.join(cxxflags)} -o {target} {' '.join(requirements)}")

@target_output(f"{build_dir}/(.+)\.o", [f"{src_dir}/{{0}}.cpp", *include_deps])
def compile(target, requirements):
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    sh(f"{cxx} {' '.join(cxxflags)} -o {target} -c {' '.join(requirements)} {' '.join(include_flags)}")

@target_phony("clean")
def clean():
    sh(f"rm -r {build_dir}")

```

</td>
</tr>
</table>
