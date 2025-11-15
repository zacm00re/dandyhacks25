import { useState, useEffect } from "react";
// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowUpIcon } from "lucide-react";
import "./index.css";
import { useChat } from "@ai-sdk/react";
import { Chat } from "@/components/ui/chat";
import Emails from "@/components/Emails";

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
  type Message = {
    id: number;
    content: string;
    type: "user" | "system";
  };
  useEffect(() => {
    checkPythonBackend();
    fetchData();
  }, []);

  /* Agent chat */
  const { messages, input, handleInputChange, handleSubmit, isLoading, stop } =
    useChat({
      api: "http://localhost:7878/api/data",
    });
  // const isLoading = status === "submitted" || status === "streaming";

  return (
    <div className="flex h-screen">
      {/* Right Panel - Chat */}
      <div className="w-3/5 py-4 border-l">
        <div className="h-1/3 border-b">
          <p className="text-lg pb-2 pl-4">Emails</p>
          <Emails></Emails>
        </div>
        <div className="h-1/3 py-4 border-b">
          <p className="text-lg pb-2 pl-4">Events</p>
        </div>
        <div className="h-1/3 py-4">
          <p className="text-lg pb-2 pl-4">Tasks</p>
        </div>
      </div>
      {/*<div className="w-1/3">*/}
      <Chat
        className="p-4"
        messages={messages}
        input={input}
        handleInputChange={handleInputChange}
        handleSubmit={handleSubmit}
        isGenerating={isLoading} // ✅ Pass isLoading here
        stop={stop}
      />
      {/* Left Panel - Daily Digest */}

      {/*</div>*/}
    </div>
  );
}

export default App;
