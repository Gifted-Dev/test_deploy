from transformers import pipeline


class Summarizer:
    def __init__(self) -> None:
        self.model = pipeline("summarization", model="facebook/bart-large-cnn")

    def generate_summary(self, text: str) -> str:
        """Generate text summary."""
        max_chunk_length = 1024
        chunks = [
            text[i : i + max_chunk_length]
            for i in range(0, len(text), max_chunk_length)
        ]
        return " ".join(
            self.model(chunk, max_length=130, min_length=30, do_sample=False)[0][
                "summary_text"
            ]
            for chunk in chunks
            if len(chunk.split()) >= 50
        )


summarizer = Summarizer()
