---
layout: post
title: "why i refactored 1200 lines of vanilla js to vue"
date: 2025-10-03
categories: vue javascript refactoring
---

i spent the last few hours refactoring my productivity app from vanilla javascript to vue 3. deleted 1200 lines of manual DOM manipulation and replaced it with 680 lines of reactive components. here's why it was worth it and what i learned.

## the app: get stuff done

quick context - this is an ai-powered goal-setting app that:
- generates SMART goals using ai
- breaks them into daily/monthly/yearly tasks
- syncs to the cloud with clerk auth + stripe billing
- handles subtasks, dark mode, pdf export, etc.

the original version was vanilla js + alpine.js (barely used) + a lot of `innerHTML`. it worked fine. but was kind of messy

## the breaking point

here's what finally pushed me to refactor:

```javascript
// Before: updating a task checkbox
function toggleTaskComplete(category, index) {
    const goalSet = goalSets[activeGoalSetId];
    goalSet[category][index].completed = !goalSet[category][index].completed;

    // Now update localStorage
    localStorage.setItem('productivityGoalSets', JSON.stringify(goalSets));

    // Don't forget to update the DOM!
    renderTasks(goalSet[category], category);

    // And the stats section
    updateTaskStats();

    // Oh and save to the cloud
    saveToCloud();
}
```

four different places to update for one checkbox. miss any of them? bugs. guaranteed.

## what vue fixes

### 1. reactivity eliminates manual dom updates

**before:**
```javascript
function renderTasks(tasks, category) {
    let html = '<div class="task-list">';
    tasks.forEach((task, index) => {
        html += `
            <div class="task-item ${task.completed ? 'completed' : ''}">
                <input type="checkbox"
                       onchange="toggleTaskComplete('${category}', ${index})"
                       ${task.completed ? 'checked' : ''}>
                <span>${escapeHtml(task.text)}</span>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById(`${category}-tasks`).innerHTML = html;
}
```

**after:**
```vue
<!-- TaskItem.vue -->
<template>
  <div class="task-item" :class="{ completed: task.completed }">
    <input
      type="checkbox"
      :checked="task.completed"
      @change="$emit('toggle-complete')">
    <span>{{ task.text }}</span>
  </div>
</template>

<script setup>
defineProps({
  task: { type: Object, required: true }
});
defineEmits(['toggle-complete']);
</script>
```

no string concatenation. no manual xss protection. no inline event handlers. just declare what it should look like and vue handles the updates.

### 2. composables solve state management

the vanilla version had state everywhere:
- global variables (`goalSets`, `activeGoalSetId`)
- localStorage (primary source of truth)
- dom state (checkbox values, input text)
- cloud database (async sync)

vue's composables pattern fixed this:

```javascript
// composables/useGoals.js
const goalSets = ref({});
const activeGoalSetId = ref(null);

export function useGoals() {
  const activeGoalSet = computed(() => {
    return activeGoalSetId.value ? goalSets.value[activeGoalSetId.value] : null;
  });

  const taskStats = computed(() => {
    const allTasks = [
      ...(activeGoalSet.value?.today || []),
      ...(activeGoalSet.value?.month || []),
      ...(activeGoalSet.value?.year || [])
    ];

    return {
      total: allTasks.length,
      completed: allTasks.filter(t => t.completed).length,
      important: allTasks.filter(t => t.important).length
    };
  });

  const toggleTaskComplete = (category, index) => {
    const task = activeGoalSet.value[category][index];
    task.completed = !task.completed;
    saveGoalSets();  // handles localStorage + cloud sync
  };

  return {
    goalSets,
    activeGoalSet,
    taskStats,
    toggleTaskComplete
  };
}
```

single source of truth. computed properties auto-update the ui. no manual synchronization.

every component that needs goal state just calls `useGoals()` and gets the same reactive data:

```vue
<!-- AppInterface.vue -->
<script setup>
import { useGoals } from '@/composables/useGoals';

const { activeGoalSet, taskStats, toggleTaskComplete } = useGoals();
</script>

<template>
  <div>Total: {{ taskStats.total }}</div>
  <div>Completed: {{ taskStats.completed }}</div>
</template>
```

change `activeGoalSet` anywhere in the app, and everything updates automatically.

### 3. components make code reusable

before, i had three copies of task rendering logic (one for each timeframe: today/month/year). different enough that extracting a function was awkward, similar enough that bugs appeared in all three.

after:

```vue
<!-- TaskList.vue - used for all three timeframes -->
<template>
  <div class="task-list">
    <TaskItem
      v-for="(task, index) in tasks"
      :key="index"
      :task="task"
      :category="category"
      :index="index"
      @toggle-complete="onToggleComplete(index)"
      @toggle-important="onToggleImportant(index)"
      @delete="onDelete(index)" />
  </div>
</template>

<script setup>
import { useGoals } from '@/composables/useGoals';

const props = defineProps({
  tasks: Array,
  category: String
});

const { toggleTaskComplete, toggleTaskImportant, deleteTask } = useGoals();

function onToggleComplete(index) {
  toggleTaskComplete(props.category, index);
}

// etc...
</script>
```

one component, three usages. fix a bug once, it's fixed everywhere.

## the migration process

### day 1: infrastructure

started with the basics:

```bash
npm install vue@latest vue-router@latest @clerk/vue@latest
npm install --save-dev vite @vitejs/plugin-vue
```

created a minimal vite config:

```javascript
// vite.config.js
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173 }
});
```

backed up the old files (`index.html` → `index-old.html`) and created a new minimal entry point:

```html
<!-- index.html -->
<!DOCTYPE html>
<html>
<head>
  <title>Get Stuff Done</title>
  <link href="./css/output.css" rel="stylesheet">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

### day 2: composables first

extracted state management before building ui. this was key - having the composables working meant i could test each piece independently.

created `useAuth()` first (authentication is the foundation):

```javascript
// composables/useAuth.js
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useClerk, useUser } from '@clerk/vue';

const userUsage = ref({ goalGenerations: 0, isSubscribed: false });

export function useAuth() {
  const router = useRouter();
  const clerk = useClerk();
  const { user, isSignedIn } = useUser();

  const currentUser = computed(() => user.value);
  const isAuthenticated = computed(() => isSignedIn.value);

  watch(isSignedIn, async (signedIn) => {
    if (signedIn && user.value) {
      router.push('/app');
      loadUserData();
    } else {
      router.push('/');
    }
  });

  return {
    currentUser,
    isAuthenticated,
    userUsage,
    signIn,
    signOut
  };
}
```

then `useGoals()` for the core app logic. tested both in isolation before touching any ui code.

### day 3: components

built components bottom-up (leaf components first):

1. `TaskItem.vue` - single task with checkbox
2. `TaskList.vue` - container for tasks
3. `AuthSection.vue` - sign in/out buttons
4. `ProfileModal.vue` / `PaywallModal.vue` - modals
5. `LandingPage.vue` / `AppInterface.vue` - top-level views

each component was small and focused. made debugging easy.

## the results

### code metrics

- vanilla js: ~1,200 lines across 3 files
- vue: ~680 lines across 15 files
- 43% reduction in code
- 100% reduction in manual dom manipulation

### before/after: adding a feature

**before (vanilla js):**

to add a "priority" field to tasks:

1. update task object when creating (3 places)
2. update rendering logic (3 timeframes × 2 views = 6 places)
3. add ui controls (3 timeframes)
4. add event handlers (global functions)
5. update stats calculation
6. update cloud sync schema
7. update localStorage schema

estimated: 2-3 hours, high chance of missing something

**after (vue):**

1. add `priority` to task object in `useGoals()`
2. add ui in `TaskItem.vue` component
3. add handler that emits event
4. update computed stats in `useGoals()`

estimated: 30 minutes, low chance of bugs

### performance

bundle size went up (added vue framework):
- before: 45 kb
- after: 87 kb (vue included), 32 kb gzipped

time to interactive actually got faster because vue's virtual dom is more efficient than my string concatenation.

## one weird trick: the shared state pattern

this was my favorite vue discovery. you can create shared state by defining refs *outside* the composable function:

```javascript
// composables/useAuth.js

// State OUTSIDE the function = shared across all components
const currentUser = ref(null);
const isAuthenticated = ref(false);

export function useAuth() {
  // Every component that calls useAuth() gets the same refs
  return { currentUser, isAuthenticated };
}
```

now any component can get the auth state:

```vue
<!-- Header.vue -->
<script setup>
import { useAuth } from '@/composables/useAuth';
const { currentUser } = useAuth();
</script>
<template>
  <div>{{ currentUser?.name }}</div>
</template>
```

```vue
<!-- Dashboard.vue -->
<script setup>
import { useAuth } from '@/composables/useAuth';
const { currentUser } = useAuth();  // Same user ref as Header!
</script>
```

it's like a global store but type-safe and composable. no need for vuex/pinia for simple apps.

## conclusion

if you're maintaining a vanilla js app and:
- you dread adding features
- you're debugging state sync issues
- you're copying code between components

...give vue a shot. the reactive primitives alone are worth it.

**app**: [actuallydostuff.com](https://actuallydostuff.com)

---

## appendix: vue 3 primer

if you want to dive deeper into vue concepts, here's a practical primer covering everything you need to know.

### for react developers

if you're coming from react, here's the quick translation guide:

| React | Vue 3 | Key Difference |
|-------|-------|----------------|
| `useState(0)` | `ref(0)` | Access with `.value` in script, auto-unwrap in template |
| `useMemo()` | `computed()` | Same concept, different syntax |
| `useEffect()` | `watch()` | More explicit dependencies |
| JSX | Templates | HTML-like syntax, no curly braces for text |
| Custom Hooks | Composables | Very similar pattern |
| Props + Callbacks | Props + Events | Events instead of callback props |
| `useContext()` | Shared Composable | Define refs outside function |
| React Router | Vue Router | Similar API, `useRouter()` / `useRoute()` |

**quick example comparison:**

react:
```jsx
function Counter() {
  const [count, setCount] = useState(0);
  const doubled = useMemo(() => count * 2, [count]);

  useEffect(() => {
    console.log('Count changed:', count);
  }, [count]);

  return (
    <div>
      <div>{count}</div>
      <div>Doubled: {doubled}</div>
      <button onClick={() => setCount(count + 1)}>Increment</button>
    </div>
  );
}
```

vue:
```vue
<script setup>
import { ref, computed, watch } from 'vue';

const count = ref(0);
const doubled = computed(() => count.value * 2);

watch(count, (newVal) => {
  console.log('Count changed:', newVal);
});
</script>

<template>
  <div>
    <div>{{ count }}</div>
    <div>Doubled: {{ doubled }}</div>
    <button @click="count++">Increment</button>
  </div>
</template>
```

**key differences:**
- vue uses `ref()` instead of `useState()`, access with `.value` in script
- templates use `{{ }}` instead of jsx's `{ }`, and no `.value` needed
- vue's `@click` vs react's `onClick`
- can mutate state directly in vue (`count++`), no setter needed

### reactivity system

vue 3's reactivity is powered by javascript proxies.

**ref() - reactive primitives:**

```javascript
import { ref } from 'vue';

const count = ref(0);           // number
const message = ref('Hello');   // string
const isActive = ref(true);     // boolean

// access/modify with .value
console.log(count.value);  // 0
count.value++;             // 1

// in templates, .value is automatic:
// <div>{{ count }}</div>  ← no .value needed!
```

**computed() - derived state:**

```javascript
import { ref, computed } from 'vue';

const tasks = ref([
  { text: 'Buy milk', completed: true },
  { text: 'Walk dog', completed: false }
]);

// recalculates when tasks changes
const completedCount = computed(() => {
  return tasks.value.filter(t => t.completed).length;
});
```

**watch() - side effects:**

```javascript
import { ref, watch } from 'vue';

const username = ref('');

watch(username, (newValue, oldValue) => {
  console.log(`Changed from ${oldValue} to ${newValue}`);
  // save to localStorage, call api, etc.
});
```

### template syntax

**text interpolation:**
```vue
<div>{{ message }}</div>
<div>{{ count * 2 }}</div>
```

**attribute binding:**
```vue
<img :src="imageUrl" :alt="imageAlt">
<div :class="{ active: isActive }">
```

**event handling:**
```vue
<button @click="handleClick">Click</button>
<button @click="count++">Increment</button>
<form @submit.prevent="onSubmit">  <!-- preventDefault() -->
```

**conditional rendering:**
```vue
<div v-if="isLoggedIn">Welcome back!</div>
<div v-else>Please log in</div>
```

**list rendering:**
```vue
<ul>
  <li v-for="task in tasks" :key="task.id">
    {{ task.text }}
  </li>
</ul>
```

**two-way binding:**
```vue
<input v-model="message">
<!-- for text inputs, equivalent to: -->
<input :value="message" @input="message = $event.target.value">
```

### composables pattern

composables are reusable functions that encapsulate reactive state and logic.

```javascript
// composables/useCounter.js
import { ref, computed } from 'vue';

export function useCounter(initialValue = 0) {
  const count = ref(initialValue);
  const doubleCount = computed(() => count.value * 2);

  function increment() {
    count.value++;
  }

  return { count, doubleCount, increment };
}
```

**using it:**
```vue
<script setup>
import { useCounter } from './composables/useCounter';

const { count, doubleCount, increment } = useCounter(10);
</script>

<template>
  <div>Count: {{ count }}</div>
  <div>Double: {{ doubleCount }}</div>
  <button @click="increment">+</button>
</template>
```

**shared state pattern:**

define refs outside the function to share across all components:

```javascript
// composables/useAuth.js
import { ref } from 'vue';

// state outside = shared across all components
const currentUser = ref(null);
const isAuthenticated = ref(false);

export function useAuth() {
  function signIn(credentials) {
    currentUser.value = userData;
    isAuthenticated.value = true;
  }

  return { currentUser, isAuthenticated, signIn };
}
```

now every component that calls `useAuth()` gets the same `currentUser` and `isAuthenticated`.

### props & events

**parent passes data down:**
```vue
<TaskItem :task="myTask" :index="0" />
```

**child receives props:**
```vue
<!-- TaskItem.vue -->
<script setup>
const props = defineProps({
  task: { type: Object, required: true },
  index: Number
});
</script>
```

**child emits events to parent:**
```vue
<script setup>
const emit = defineEmits(['toggle-complete', 'delete']);

function handleCheckbox() {
  emit('toggle-complete');
}
</script>

<template>
  <input @change="handleCheckbox">
</template>
```

**parent listens:**
```vue
<TaskItem @toggle-complete="onToggleComplete" />
```

### lifecycle hooks

```javascript
import { onMounted, onUnmounted } from 'vue';

onMounted(() => {
  console.log('Component mounted');
  // fetch data, add event listeners
});

onUnmounted(() => {
  console.log('Cleaning up');
  // remove event listeners, cancel timers
});
```

### common gotchas

**1. don't mutate props:**
```vue
<!-- ❌ don't do this -->
<script setup>
const props = defineProps({ task: Object });
props.task.completed = true;  // mutating prop!
</script>

<!-- ✅ do this instead -->
<script setup>
const emit = defineEmits(['update']);
emit('update', { ...props.task, completed: true });
</script>
```

**2. v-for needs :key:**
```vue
<!-- ❌ missing key -->
<div v-for="task in tasks">{{ task.text }}</div>

<!-- ✅ with key -->
<div v-for="task in tasks" :key="task.id">{{ task.text }}</div>
```

**3. remember .value in script:**
```javascript
const count = ref(0);

// ❌ won't work
console.log(count);    // RefImpl object
count++;              // NaN

// ✅ correct
console.log(count.value);
count.value++;
```

templates don't need `.value`, but scripts do.

### quick reference

**reactivity:**
```javascript
import { ref, reactive, computed, watch } from 'vue';

const count = ref(0);
const state = reactive({ name: 'Alice' });
const doubled = computed(() => count.value * 2);

watch(count, (newVal, oldVal) => {
  console.log(`Changed from ${oldVal} to ${newVal}`);
});
```

**component communication:**
```vue
<!-- parent -->
<Child :msg="message" @update="handleUpdate" />

<!-- child -->
<script setup>
defineProps({ msg: String });
const emit = defineEmits(['update']);
emit('update', newValue);
</script>
```

**composable pattern:**
```javascript
// outside = shared
const state = ref({});

export function useFeature() {
  function method() { /* ... */ }
  return { state, method };
}
```

**lifecycle:**
```javascript
import { onMounted, onUnmounted } from 'vue';

onMounted(() => console.log('Component mounted'));
onUnmounted(() => console.log('Cleanup'));
```

**resources:**
- [vue 3 docs](https://vuejs.org/)
- [vue router docs](https://router.vuejs.org/)
- [vueuse](https://vueuse.org/) - collection of useful composables
