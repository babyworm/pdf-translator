import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.*;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.*;

import java.awt.Color;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.text.Normalizer;
import java.util.*;

/**
 * PDF Builder using Apache PDFBox 3.x.
 *
 * Improvements:
 * 1. Unicode NFKC normalization + manual symbol mapping
 * 2. Multi-font chain (CJK → NotoSans → Helvetica)
 * 3. Heading bbox expansion when text overflows
 * 4. "skip" field support — skip elements should not be white-outed or drawn
 *
 * Usage: java -cp opendataloader-pdf-cli.jar:. PdfBuilder src.pdf translations.json output.pdf
 */
public class PdfBuilder {

    private static PDFont cjkFont = null;
    private static PDFont latinFont = null;  // NotoSans or similar broad-coverage
    private static PDFont defaultFont = null; // Helvetica

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: PdfBuilder <source.pdf> <translations.json> <output.pdf>");
            System.exit(1);
        }

        String srcPath = args[0];
        String jsonPath = args[1];
        String dstPath = args[2];

        String jsonContent = Files.readString(Path.of(jsonPath), StandardCharsets.UTF_8);
        List<Map<String, Object>> items = parseJson(jsonContent);

        try (PDDocument doc = Loader.loadPDF(new File(srcPath))) {
            defaultFont = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            loadFonts(doc);

            // Group by page
            Map<Integer, List<Map<String, Object>>> byPage = new TreeMap<>();
            for (Map<String, Object> item : items) {
                int page = ((Number) item.get("page")).intValue();
                byPage.computeIfAbsent(page, k -> new ArrayList<>()).add(item);
            }

            for (var entry : byPage.entrySet()) {
                int pageNum = entry.getKey();
                var pageItems = entry.getValue();
                if (pageNum < 1 || pageNum > doc.getNumberOfPages()) continue;
                PDPage page = doc.getPage(pageNum - 1);
                float pageWidth = page.getMediaBox().getWidth();

                // Phase 1: White-out (skip elements with "skip":true)
                try (PDPageContentStream cs = new PDPageContentStream(doc, page,
                        PDPageContentStream.AppendMode.APPEND, true, true)) {
                    for (var item : pageItems) {
                        if (isSkip(item)) continue;
                        float[] bbox = getBbox(item);
                        if (bbox == null) continue;
                        float w = bbox[2] - bbox[0], h = bbox[3] - bbox[1];
                        if (w < 10 && h < 15) continue;

                        // For headings, compute expanded bbox
                        String type = (String) item.getOrDefault("type", "paragraph");
                        String text = (String) item.get("text");
                        float maxFs = getFloat(item, "font_size", 12f);
                        float x0 = bbox[0], yBottom = bbox[1], x1 = bbox[2], yTop = bbox[3];

                        if ("heading".equals(type) && text != null) {
                            text = normalizeText(text);
                            PDFont font = chooseFontForText(text);
                            float textW = measureText(text, font, maxFs);
                            if (textW > w) {
                                float margin = 36f;
                                x1 = Math.min(x0 + textW + 10, pageWidth - margin);
                                w = x1 - x0;
                            }
                        }

                        cs.setNonStrokingColor(Color.WHITE);
                        cs.addRect(x0, yBottom, w, yTop - yBottom);
                        cs.fill();
                    }
                }

                // Phase 2: Draw translated text (skip elements with "skip":true)
                try (PDPageContentStream cs = new PDPageContentStream(doc, page,
                        PDPageContentStream.AppendMode.APPEND, true, true)) {
                    for (var item : pageItems) {
                        if (isSkip(item)) continue;
                        float[] bbox = getBbox(item);
                        if (bbox == null) continue;
                        String text = (String) item.get("text");
                        if (text == null || text.isEmpty()) continue;

                        // (1) Normalize special characters
                        text = normalizeText(text);

                        float x0 = bbox[0], yBottom = bbox[1], x1 = bbox[2], yTop = bbox[3];
                        float rectW = x1 - x0, rectH = yTop - yBottom;
                        if (rectW < 10 && rectH < 15) continue;

                        float maxFs = getFloat(item, "font_size", 12f);
                        String type = (String) item.getOrDefault("type", "paragraph");
                        Color color = getColor(item);
                        boolean vertical = rectH > 0 && rectW > 0 && rectH / rectW > 3.0;
                        boolean heading = "heading".equals(type);

                        // (2) Choose font from chain
                        PDFont font = chooseFontForText(text);
                        float fontSize;

                        if (heading) {
                            fontSize = maxFs;
                            // (3) Expand bbox for headings if text overflows
                            float textW = measureText(text, font, fontSize);
                            if (textW > rectW) {
                                float margin = 36f;
                                x1 = Math.min(x0 + textW + 10, pageWidth - margin);
                                rectW = x1 - x0;
                            }
                        } else if (vertical) {
                            fontSize = fitFontSize(text, rectH, rectW, maxFs, font);
                        } else {
                            fontSize = fitFontSize(text, rectW, rectH, maxFs, font);
                        }
                        fontSize = Math.max(fontSize, 6f);

                        cs.setNonStrokingColor(color);

                        if (vertical) {
                            drawVerticalText(cs, text, x0, yBottom, x1, yTop, fontSize, font);
                        } else {
                            drawTextInRect(cs, text, x0, yBottom, x1, yTop, fontSize, font);
                        }
                    }
                }
            }

            doc.save(dstPath);
        }
        System.out.println("OK");
    }

    // ── (1) Unicode normalization + manual mapping ──

    private static String normalizeText(String text) {
        text = Normalizer.normalize(text, Normalizer.Form.NFKC);
        // Manual replacements for chars NFKC doesn't cover
        text = text.replace('\u2217', '*')   // ∗ → *
                   .replace('\u2212', '-')   // − → -
                   .replace('\u2018', '\'')  // ' → '
                   .replace('\u2019', '\'')  // ' → '
                   .replace('\u201C', '"')   // " → "
                   .replace('\u201D', '"')   // " → "
                   .replace('\u2013', '-')   // – → -
                   .replace('\u2014', '-')   // — → -
                   .replace('\u00A0', ' ');  // NBSP → space
        return text;
    }

    // ── (2) Font chain: CJK → Latin → Default ──

    private static void loadFonts(PDDocument doc) {
        // CJK font
        String[] cjkPaths = {
            System.getProperty("user.home") + "/Library/Fonts/NanumGothic-Regular.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        };
        for (String path : cjkPaths) {
            if (new File(path).exists()) {
                try {
                    cjkFont = PDType0Font.load(doc, new File(path));
                    System.err.println("CJK font: " + path);
                    break;
                } catch (Exception e) {
                    System.err.println("Skip CJK: " + path + " (" + e.getMessage() + ")");
                }
            }
        }

        // Broad-coverage Latin font (NotoSans)
        String[] latinPaths = {
            System.getProperty("user.home") + "/Library/Fonts/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        };
        for (String path : latinPaths) {
            if (new File(path).exists()) {
                try {
                    latinFont = PDType0Font.load(doc, new File(path));
                    System.err.println("Latin font: " + path);
                    break;
                } catch (Exception e) {
                    System.err.println("Skip Latin: " + path + " (" + e.getMessage() + ")");
                }
            }
        }

        if (cjkFont == null) System.err.println("WARN: No CJK font found");
        if (latinFont == null) System.err.println("WARN: No broad Latin font, using Helvetica only");
    }

    private static PDFont chooseFontForText(String text) {
        // If any CJK char → use CJK font (it usually covers Latin too)
        if (cjkFont != null) {
            for (char ch : text.toCharArray()) {
                if (isCjk(ch)) return cjkFont;
            }
        }
        // For Latin-heavy text, prefer NotoSans (broader coverage than Helvetica)
        if (latinFont != null) return latinFont;
        return defaultFont;
    }

    /** Try fonts in order: preferred → latinFont → defaultFont */
    private static PDFont fontForChar(char ch, PDFont preferred) {
        PDFont[] chain;
        if (isCjk(ch)) {
            chain = new PDFont[]{cjkFont, latinFont, defaultFont};
        } else {
            chain = new PDFont[]{preferred, latinFont, cjkFont, defaultFont};
        }
        for (PDFont f : chain) {
            if (f == null) continue;
            try {
                f.getStringWidth(String.valueOf(ch));
                return f;
            } catch (Exception ignored) {}
        }
        return defaultFont;
    }

    // ── Drawing ──

    private static void drawTextInRect(PDPageContentStream cs, String text,
            float x0, float y0, float x1, float y1,
            float fontSize, PDFont font) throws IOException {
        float boxWidth = x1 - x0;
        float lineHeight = fontSize * 1.3f;
        List<String> lines = wrapText(text, fontSize, boxWidth, font);
        float yCursor = y1 - fontSize;
        for (String line : lines) {
            // Allow vertical overflow — content completeness over layout precision
            drawLine(cs, line, x0, yCursor, fontSize, font);
            yCursor -= lineHeight;
        }
    }

    private static void drawVerticalText(PDPageContentStream cs, String text,
            float x0, float y0, float x1, float y1,
            float fontSize, PDFont font) throws IOException {
        float boxWidth = y1 - y0;
        List<String> lines = wrapText(text, fontSize, boxWidth, font);
        float lineHeight = fontSize * 1.3f;
        float yCursor = -fontSize;
        for (String line : lines) {
            if (Math.abs(yCursor) > (x1 - x0)) break;
            try {
                cs.saveGraphicsState();
                cs.transform(new org.apache.pdfbox.util.Matrix(0, 1, -1, 0, x0, y0));
                drawLine(cs, line, 0, yCursor, fontSize, font);
                cs.restoreGraphicsState();
            } catch (Exception e) {
                try { cs.restoreGraphicsState(); } catch (Exception ignore) {}
            }
            yCursor -= lineHeight;
        }
    }

    private static void drawLine(PDPageContentStream cs, String line,
            float x, float y, float fontSize, PDFont preferredFont) throws IOException {
        // Try whole-line with preferred font
        try {
            cs.beginText();
            cs.setFont(preferredFont, fontSize);
            cs.newLineAtOffset(x, y);
            cs.showText(line);
            cs.endText();
            return;
        } catch (Exception e) {
            try { cs.endText(); } catch (Exception ignore) {}
        }

        // Fallback: char-by-char with font chain
        float xCursor = x;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            String s = String.valueOf(ch);
            PDFont charFont = fontForChar(ch, preferredFont);
            float cw;
            try {
                cs.beginText();
                cs.setFont(charFont, fontSize);
                cs.newLineAtOffset(xCursor, y);
                cs.showText(s);
                cs.endText();
                cw = charFont.getStringWidth(s) / 1000f * fontSize;
            } catch (Exception ex) {
                try { cs.endText(); } catch (Exception ignore) {}
                // Last resort: skip the character
                cw = fontSize * 0.5f;
            }
            xCursor += cw;
        }
    }

    // ── Text metrics ──

    private static float measureText(String text, PDFont font, float fontSize) {
        float total = 0;
        for (int i = 0; i < text.length(); i++) {
            try {
                PDFont f = fontForChar(text.charAt(i), font);
                total += f.getStringWidth(String.valueOf(text.charAt(i))) / 1000f * fontSize;
            } catch (Exception e) {
                total += fontSize * 0.6f;
            }
        }
        return total;
    }

    // Kinsoku (금칙) — punctuation that must not start a line
    private static final String KINSOKU_NO_START = "）、。，．：；？！」』】〉》〕｝,.;:?!)]}…‥";
    // Kinsoku — brackets that must not end a line
    private static final String KINSOKU_NO_END = "（「『【〈《〔｛([{";
    private static final int KINSOKU_MARGIN = 2;

    private static List<String> wrapText(String text, float fontSize, float boxWidth, PDFont font) {
        List<String> lines = new ArrayList<>();
        if (boxWidth <= 0) { lines.add(text); return lines; }
        StringBuilder cur = new StringBuilder();
        float curW = 0;
        int overflow = 0;
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch == '\n') { lines.add(cur.toString()); cur = new StringBuilder(); curW = 0; overflow = 0; continue; }
            float cw;
            try {
                PDFont f = fontForChar(ch, font);
                cw = f.getStringWidth(String.valueOf(ch)) / 1000f * fontSize;
            } catch (Exception e) { cw = fontSize * 0.6f; }
            if (curW + cw > boxWidth && cur.length() > 0) {
                if (overflow < KINSOKU_MARGIN) {
                    if (KINSOKU_NO_START.indexOf(ch) >= 0 ||
                        (cur.length() > 0 && KINSOKU_NO_END.indexOf(cur.charAt(cur.length() - 1)) >= 0)) {
                        cur.append(ch); curW += cw; overflow++; continue;
                    }
                }
                lines.add(cur.toString()); cur = new StringBuilder(); curW = 0; overflow = 0;
            }
            cur.append(ch); curW += cw;
        }
        if (cur.length() > 0) lines.add(cur.toString());
        return lines.isEmpty() ? List.of("") : lines;
    }

    private static float fitFontSize(String text, float width, float height, float maxSize, PDFont font) {
        float lo = Math.max(maxSize * 0.6f, 6f), hi = maxSize;
        for (int i = 0; i < 12; i++) {
            float mid = (lo + hi) / 2f;
            float totalW = measureText(text, font, mid);
            int numLines = width > 0 ? (int) Math.ceil(totalW / width) : 1;
            float estH = numLines * mid * 1.3f;
            if ((totalW <= width || numLines > 1) && estH <= height) lo = mid;
            else hi = mid;
        }
        return lo;
    }

    // ── Helpers ──

    private static boolean isCjk(char ch) {
        return (ch >= 0x4E00 && ch <= 0x9FFF) || (ch >= 0x3400 && ch <= 0x4DBF) ||
               (ch >= 0xAC00 && ch <= 0xD7AF) || (ch >= 0x3040 && ch <= 0x30FF);
    }

    private static boolean isSkip(Map<String, Object> item) {
        Object skip = item.get("skip");
        if (skip instanceof Boolean) return (Boolean) skip;
        return false;
    }

    private static float[] getBbox(Map<String, Object> item) {
        Object raw = item.get("bbox");
        if (raw instanceof List) {
            List<?> list = (List<?>) raw;
            if (list.size() == 4) {
                return new float[]{
                    ((Number) list.get(0)).floatValue(), ((Number) list.get(1)).floatValue(),
                    ((Number) list.get(2)).floatValue(), ((Number) list.get(3)).floatValue()
                };
            }
        }
        return null;
    }

    private static float getFloat(Map<String, Object> item, String key, float def) {
        Object v = item.get(key);
        return v instanceof Number ? ((Number) v).floatValue() : def;
    }

    private static Color getColor(Map<String, Object> item) {
        Object raw = item.get("text_color");
        if (raw instanceof List) {
            List<?> tc = (List<?>) raw;
            if (!tc.isEmpty()) {
                boolean is255 = tc.stream().anyMatch(v -> ((Number) v).floatValue() > 1.0f);
                if (tc.size() == 1) {
                    float val = ((Number) tc.get(0)).floatValue();
                    if (is255) val /= 255f;
                    return new Color(clamp(val), clamp(val), clamp(val));
                } else if (tc.size() >= 3) {
                    float r = ((Number) tc.get(0)).floatValue();
                    float g = ((Number) tc.get(1)).floatValue();
                    float b = ((Number) tc.get(2)).floatValue();
                    if (is255) { r /= 255f; g /= 255f; b /= 255f; }
                    return new Color(clamp(r), clamp(g), clamp(b));
                }
            }
        }
        return Color.BLACK;
    }

    private static float clamp(float v) { return Math.max(0f, Math.min(1f, v)); }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> parseJson(String json) {
        List<Map<String, Object>> result = new ArrayList<>();
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper =
                    new com.fasterxml.jackson.databind.ObjectMapper();
            List<?> list = mapper.readValue(json, List.class);
            for (Object item : list) result.add((Map<String, Object>) item);
        } catch (Exception e) {
            System.err.println("JSON parse error: " + e.getMessage());
        }
        return result;
    }
}
