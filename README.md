<h1>🏹 AI Wumpus World Solver</h1>

<p>
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/PyGame-2.x-green?style=flat-square&logo=pygame" alt="PyGame">
  <img src="https://img.shields.io/badge/AI-Propositional_Logic-orange?style=flat-square" alt="AI">
</p>

<p>An interactive, visually rich simulation of the classic <strong>Wumpus World</strong> environment. This project features a fully autonomous AI agent equipped with a custom deductive reasoning engine. Watch in real-time as the AI calculates hazard probabilities, maps safe routes, takes calculated risks, and hunts the Wumpus.</p>

<hr>

<h2>✨ Features</h2>

<h3>🧠 Advanced AI Logic</h3>
<ul>
  <li><strong>Dynamic Knowledge Base:</strong> The agent dynamically maps the grid, storing visited states, sensor data (Breeze, Stench, Glitter), and calculating exact probabilities for Pits and the Wumpus.</li>
  <li><strong>Propositional Deduction:</strong> Uses intersection logic to isolate the exact location of the Wumpus and definitively flag safe squares.</li>
  <li><strong>Risk-Aware Pathfinding:</strong> Utilizes Breadth-First Search (BFS) to navigate guaranteed safe paths. When no safe path exists, it calculates the lowest-risk frontier to explore.</li>
  <li><strong>Live Monologue:</strong> A real-time scrolling UI log details exactly what the AI is "thinking" and doing at every step.</li>
</ul>

<h3>🎮 Interactive Visuals</h3>
<ul>
  <li><strong>"God Mode" Overlay:</strong> See the hidden grid, animated particle effects for gold, flowing breezes around pits, and stenches radiating from the Wumpus.</li>
  <li><strong>Probability Mapping:</strong> The AI's internal knowledge is overlaid on unvisited squares, showing real-time risk percentages (e.g., <code>Risk: 33%</code> or <code>CERTAIN PIT</code>).</li>
  <li><strong>Directional Animation:</strong> The agent uses strict tank controls, visibly turning to face its target before moving or firing its bow.</li>
</ul>

<h3>⚙️ Technical Highlights</h3>
<ul>
  <li><strong>Web-Ready Architecture:</strong> Built using an asynchronous main loop (<code>asyncio</code>), making the codebase inherently compatible with WebAssembly ports like <code>pygbag</code> for browser-based play.</li>
  <li><strong>Zero Dependencies (Mostly):</strong> Relies solely on PyGame and standard Python libraries (<code>math</code>, <code>collections</code>, <code>random</code>).</li>
</ul>

<hr>

<h2>🚀 Installation & Usage</h2>

<h3>Prerequisites</h3>
<p>You will need Python 3.x installed on your machine.</p>

<h3>Setup</h3>
<ol>
  <li>Clone the repository:
    <pre><code>git clone https://github.com/YourUsername/wumpus-agent.git
cd wumpus-agent</code></pre>
  </li>
  <li>Install the required library:
    <pre><code>pip install pygame</code></pre>
  </li>
  <li>Run the simulation:
    <pre><code>python main.py</code></pre>
  </li>
</ol>
<p><em>(Note: If you named your main python file differently, replace <code>main.py</code> with your file name).</em></p>

<hr>

<h2>🕹️ Controls</h2>
<p>You have complete control over the simulation's pacing. You can let the AI run wild or step through its logic frame-by-frame.</p>
<ul>
  <li><strong>[Spacebar]</strong> - Toggle <strong>Auto-Play</strong> mode on/off.</li>
  <li><strong>[ S ]</strong> - Manually trigger a single <strong>AI Step</strong> (highly recommended for watching the deduction engine work).</li>
  <li><strong>[ R ]</strong> - <strong>Reset</strong> the board. This generates a completely new, mathematically solvable grid layout.</li>
  <li><strong>[Mouse Scroll]</strong> - Scroll up and down through the AI's action log on the right sidebar.</li>
</ul>

<hr>

<h2>📖 The AI Ruleset</h2>
<p>The agent follows standard Wumpus World rules to maximize its score:</p>
<ul>
  <li><strong>+1000</strong> for escaping alive with the Gold.</li>
  <li><strong>-1000</strong> for dying (falling into a Pit or being eaten by the Wumpus).</li>
  <li><strong>-10</strong> for shooting an arrow (the agent only has one).</li>
  <li><strong>-1</strong> for every movement or turn (encourages efficient pathfinding).</li>
</ul>

<p><strong>How it survives:</strong> The AI prioritizes guaranteed safety. It will always use BFS to find the nearest 100% safe, unvisited square. If it detects a Stench and narrows the Wumpus location down to a single square, it will pathfind to an adjacent square, turn, and fire its arrow to clear the board. If no safe squares exist, it calculates a <code>(Pit Probability * 2) + Wumpus Probability + Distance</code> score to choose the mathematically safest risk.</p>
