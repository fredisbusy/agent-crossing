import { GameCanvas, Header, Inspector } from "./components";

function App() {
  return (
    <div className="flex h-screen flex-col bg-stone-900">
      <Header />
      <main className="flex min-h-0 flex-1">
        <GameCanvas />
        <Inspector />
      </main>
    </div>
  );
}

export default App;
