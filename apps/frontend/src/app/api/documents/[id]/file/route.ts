import { gateway } from "@/infrastructure/gateway";

/**
 * Serves the original document behind a retrieved excerpt from this site's own origin, so the
 * in-page viewer can load it without the browser ever talking to the Evidence Engine.
 *
 * Byte ranges are passed through: NASA reports run to tens of megabytes, and the viewer only
 * needs the parts of the file that describe one page.
 */
export async function GET(request: Request, ctx: RouteContext<"/api/documents/[id]/file">) {
  const { id } = await ctx.params;
  let file;
  try {
    file = await gateway.sourceDocument(id, request.headers.get("range"));
  } catch {
    return Response.json({ detail: "The Evidence Engine could not provide this file." }, { status: 502 });
  }
  if (!file) {
    return Response.json({ detail: "No local copy of this source document." }, { status: 404 });
  }
  const headers = new Headers({
    "Content-Type": file.contentType,
    "Content-Disposition": "inline",
    "Cache-Control": "no-store",
  });
  if (file.contentLength) headers.set("Content-Length", file.contentLength);
  if (file.contentRange) headers.set("Content-Range", file.contentRange);
  if (file.acceptRanges) headers.set("Accept-Ranges", file.acceptRanges);
  return new Response(file.body, { status: file.status, headers });
}
