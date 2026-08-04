export type Prediction = {
  label: string;
  score: number;
  model: string;
  received_at: string;
};

type ErrorPayload = {
  error?: string;
  detail?: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

function getErrorMessage(payload: unknown): string {
  if (typeof payload === "object" && payload !== null) {
    const errorPayload = payload as ErrorPayload;
    if (errorPayload.error) return errorPayload.error;
    if (errorPayload.detail) return errorPayload.detail;
  }
  return "Không thể kết nối tới AI service.";
}

export async function predictText(text: string): Promise<Prediction> {
  const response = await fetch(`${apiUrl}/api/v1/ai/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  const payload: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    throw new Error(getErrorMessage(payload));
  }

  return payload as Prediction;
}
