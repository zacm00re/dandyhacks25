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
import { useGoogleLogin } from "@react-oauth/google";
import { jwtDecode } from "jwt-decode";
// import * as dotenv from "dotenv";
// dotenv.config();

const SCOPES =
  "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/tasks";

interface DataItem {
  id: number;
  name: string;
}

function App() {
  // const [pythonStatus, setPythonStatus] = useState<string>("Checking...");
  // const [data, setData] = useState<DataItem[]>([]);

  // const checkPythonBackend = async () => {
  //   try {
  //     if (window.electron) {
  //       const result = await window.electron.pingPython();
  //       setPythonStatus(result.message || "Connected");
  //     } else {
  //       // Direct fetch for web development mode
  //       const response = await fetch("http://localhost:8000/ping");
  //       const result = await response.json();
  //       setPythonStatus(result.message || "Connected");
  //     }
  //   } catch (error) {
  //     setPythonStatus("Disconnected");
  //     console.error("Error connecting to Python backend:", error);
  //   }
  // };

  // const fetchData = async () => {
  //   try {
  //     const response = await fetch("http://localhost:8000/api/data");
  //     const result = await response.json();
  //     setData(result.data);
  //   } catch (error) {
  //     console.error("Error fetching data:", error);
  //   }
  // };
  // type Message = {
  //   id: number;
  //   content: string;
  //   type: "user" | "system";
  // };
  // useEffect(() => {
  //   checkPythonBackend();
  //   fetchData();
  // }, []);

  /* Agent chat */
  const { messages, input, handleInputChange, handleSubmit, isLoading, stop } =
    useChat({
      api: "http://localhost:7878/api/data",
    });
  // const isLoading = status === "submitted" || status === "streaming";
  /* Google login */
  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      // tokenResponse.access_token - use this for Gmail/Calendar APIs
      console.log("Access Token:", tokenResponse.access_token);
      localStorage.setItem("google_access_token", tokenResponse.access_token);

      // Get user info from Google's userinfo endpoint
      const userInfoResponse = await fetch(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        {
          headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
        },
      );
      const userData = await userInfoResponse.json();

      userInfo.name = userData.given_name;
      setGoogAuthed(true);
    },
    onError: () => console.log("Google auth failed"),
    scope: SCOPES,
  });
  const [googAuthed, setGoogAuthed] = useState<boolean>(false);
  let userInfo = {
    name: "",
  };
  //
  return (
    <div className="flex h-screen">
      {/* LEFT - GOOGLE */}
      {googAuthed ? (
        <div className="w-3/5 py-4 border-r">
          <div className="h-1/3 border-b flex flex-col">
            <p className="text-lg pb-2 pl-4 flex-shrink-0">Emails</p>
            <div className="flex-1 overflow-hidden">
              <Emails />
            </div>
          </div>
          <div className="h-1/3 py-4 border-b">
            <p className="text-lg pb-2 pl-4">Events</p>
          </div>
          <div className="h-1/3 py-4">
            <p className="text-lg pb-2 pl-4">Tasks</p>
          </div>
        </div>
      ) : (
        <div className="w-3/5 p-4 border-r flex-col justify-center items-center">
          <p className="pb-4 self-start text-lg">
            Authenticate with Google to access Calendar & Mail
          </p>
          <button
            onClick={login}
            className="bg-black text-white px-6 py-3 rounded-full flex items-center gap-2"
          >
            {/* Add a Google icon here if you want */}
            Sign in with Google
          </button>
        </div>
      )}
      {/* RIGHT - CHAT */}
      <div className="flex w-2/5">
        <Chat
          className="p-4"
          messages={messages}
          input={input}
          handleInputChange={handleInputChange}
          handleSubmit={handleSubmit}
          isGenerating={isLoading} // ✅ Pass isLoading here
          stop={stop}
        />
      </div>
    </div>
  );
}

export default App;
