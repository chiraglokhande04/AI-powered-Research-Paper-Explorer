const express = require("express");
const multer = require("multer");
const { v2: cloudinary } = require("cloudinary");
const streamifier = require("streamifier");
const Paper = require("../models/paperModel");
const axios = require("axios");

const router = express.Router();
const storage = multer.memoryStorage();
const upload = multer({ storage });

// Cloudinary config
cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

// POST /api/papers/upload
// router.post("/upload", upload.single("file"), async (req, res) => {
//   try {
//     console.log("=== Upload request received ===");

//     if (!req.file) {
//       console.log("❌ No file uploaded");
//       return res.status(400).json({ error: "No file uploaded" });
//     }

//     const fileBuffer = req.file.buffer;

//     console.log("Uploading to Cloudinary...");

//     const result = await new Promise((resolve, reject) => {
//       const stream = cloudinary.uploader.upload_stream(
//         { folder: "research-papers", resource_type: "auto" },
//         (error, result) => {
//           if (error) {
//             console.error("❌ Cloudinary error:", error);
//             reject(error);
//           } else {
//             console.log("✅ Cloudinary upload success:", result.secure_url);
//             resolve(result);
//           }
//         }
//       );

//       // Convert buffer to stream and pipe
//       streamifier.createReadStream(fileBuffer).pipe(stream);
//     });

//     console.log("Saving metadata to MongoDB...");
//     const paper = new Paper({
//       title: req.file.originalname,
//       originalName: req.file.originalname,
//       cloudinaryUrl: result.secure_url,
//       size: req.file.size,
//     });

//     await paper.save();
//     console.log("✅ Metadata saved:", paper._id);

//     res.json({ message: "File uploaded successfully", paper });
//   } catch (err) {
//     console.error("❌ Upload route failed:", err);
//     res.status(500).json({ error: "File upload failed", details: err.message });
//   }
// });

router.post("/upload_and_parse", upload.single("file"), async (req, res) => {
  try {
    // 1️⃣ Upload file to Cloudinary
    const result = await new Promise((resolve, reject) => {
      const stream = cloudinary.uploader.upload_stream(
        { folder: "research-papers", resource_type: "raw" },
        (err, res) => (err ? reject(err) : resolve(res))
      );
      stream.end(req.file.buffer);
    });

    console.log("Cloudinary upload result:", result.secure_url);

    // 2️⃣ Save metadata to MongoDB
    const paper = await Paper.create({
      title: req.file.originalname,
      originalName: req.file.originalname,
      cloudinaryUrl: result.secure_url,
      size: req.file.size
    });

    // 3️⃣ Call Python microservice to parse
    const parseResponse = await axios.post("http://localhost:8000/parse_pdf", {
      cloudinary_url: result.secure_url
    });

    res.json({
      message: "File uploaded & parsed successfully",
      paper,
      parsed: parseResponse.data.parsed
    });

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

