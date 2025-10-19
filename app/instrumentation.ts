import { LangfuseSpanProcessor } from "@langfuse/otel";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";

export const langfuseSpanProcessor = new LangfuseSpanProcessor({
  exportMode: "immediate", // Critical for serverless
});

const tracerProvider = new NodeTracerProvider({
  spanProcessors: [langfuseSpanProcessor],
});

tracerProvider.register();

export function register() {
  console.log("Langfuse instrumentation registered");
}
