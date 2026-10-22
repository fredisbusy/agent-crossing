import { GameCanvas, Header, Inspector } from "./components";

function App() {
  return (
    <div className="flex h-dvh flex-col bg-stone-900">
      <Header />
      <main className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        <GameCanvas />
        <Inspector />
      </main>
    </div>
  );
}

export default App;
