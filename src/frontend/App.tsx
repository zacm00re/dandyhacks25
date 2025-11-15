import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface DataItem {
  id: number;
  name: string;
}

function App() {
  const [pythonStatus, setPythonStatus] = useState<string>("Checking...");
  const [data, setData] = useState<DataItem[]>([]);

  const checkPythonBackend = async () => {
    try {
      if (window.electron) {
        const result = await window.electron.pingPython();
        setPythonStatus(result.message || "Connected");
      } else {
        // Direct fetch for web development mode
        const response = await fetch("http://localhost:8000/ping");
        const result = await response.json();
        setPythonStatus(result.message || "Connected");
      }
    } catch (error) {
      setPythonStatus("Disconnected");
      console.error("Error connecting to Python backend:", error);
    }
  };

  const fetchData = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/data");
      const result = await response.json();
      setData(result.data);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  useEffect(() => {
    checkPythonBackend();
    fetchData();
  }, []);

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Electron + React + Python App</CardTitle>
            <CardDescription>
              Boilerplate with shadcn/ui components
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div
                  className={`h-3 w-3 rounded-full ${
                    pythonStatus === "pong" ? "bg-green-500" : "bg-red-500"
                  }`}
                />
                <span className="text-sm">Python Backend: {pythonStatus}</span>
              </div>
              <Button onClick={checkPythonBackend} variant="outline" size="sm">
                Refresh
              </Button>
            </div>

            <div className="space-y-2">
              <h3 className="font-semibold">Data from Python API:</h3>
              <div className="grid gap-2">
                {data.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 border rounded-md bg-secondary/50"
                  >
                    {item.name}
                  </div>
                ))}
              </div>
              <Button onClick={fetchData} variant="secondary" size="sm">
                Fetch Data
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Get Started</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Edit{" "}
              <code className="px-1 py-0.5 bg-muted rounded">
                src/frontend/App.tsx
              </code>{" "}
              to modify the UI
            </p>
            <p className="text-sm text-muted-foreground">
              Edit{" "}
              <code className="px-1 py-0.5 bg-muted rounded">
                src/backend/main.py
              </code>{" "}
              to modify the API
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default App;
