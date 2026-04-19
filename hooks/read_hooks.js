async function main() {
    const chunks = [];
    for await (const chunk of process.stdin) {
        chunks.push(chunk);
    }
    const raw = Buffer.concat(chunks).toString();

    let toolArgs;
    try {
        toolArgs = raw ? JSON.parse(raw) : {};
    } catch (err) {
        // Fail-open to avoid breaking all reads if the hook input shape changes.
        // Still try a best-effort block if the raw payload obviously references .env.
        if (typeof raw === "string" && raw.toLowerCase().includes(".env")) {
            console.error("Blocked: attempted access to protected .env file.");
            process.exit(2);
        }
        process.exit(0);
    }

    // Gather likely path fields from different tool shapes.
    const toolInput = toolArgs?.tool_input ?? toolArgs?.toolInput ?? {};

    const candidateValues = [
        toolInput?.file_path,
        toolInput?.filePath,
        toolInput?.path,
        toolInput?.paths,
        toolInput?.file_paths,
        toolInput?.filePaths,
        toolInput?.includePattern,
        toolInput?.directory,
        toolInput?.dir,
        toolArgs?.file_path,
        toolArgs?.filePath,
        toolArgs?.path,
    ];

    const candidates = candidateValues
        .flat()
        .filter((v) => typeof v === "string" && v.length > 0);

    const blocksEnv = (p) => {
        const normalized = String(p).toLowerCase().replace(/\\/g, "/");
        const parts = normalized.split("/").filter(Boolean);
        const base = parts.length ? parts[parts.length - 1] : normalized;

        // Block `.env` and `.env.*` (e.g. .env.local). Avoid blocking unrelated files like `my.env.txt`.
        return base === ".env" || base.startsWith(".env.");
    };

    if (candidates.some(blocksEnv)) {
        console.error("The .env file is protected by a read hook and cannot be accessed.");
        process.exit(2);
    }

    process.exit(0);
}

main();