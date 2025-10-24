// require('dotenv').config(); // MUST be first
// const express = require("express");
// const multer = require("multer");
// const { v2: cloudinary } = require("cloudinary");
// const Paper = require("../models/paperModel");


// const router = express.Router();

// // Multer setup: store files in memory (RAM)
// const storage = multer.memoryStorage();
// const upload = multer({ storage });

// // Configure Cloudinary
// cloudinary.config({
//   cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
//   api_key: process.env.CLOUDINARY_API_KEY,
//   api_secret: process.env.CLOUDINARY_API_SECRET,
// });

// console.log("Cloudinary config in route:", {
//   cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
//   api_key: process.env.CLOUDINARY_API_KEY ? "✅ Loaded" : "❌ Missing",
//   api_secret: process.env.CLOUDINARY_API_SECRET ? "✅ Loaded" : "❌ Missing"
// });

// // POST /api/papers/upload
// router.post("/upload", upload.single("file"), async (req, res) => {
//   try {
//     if (!req.file) return res.status(400).json({ error: "No file uploaded" });

//     const fileBuffer = req.file.buffer;

//     // Upload to Cloudinary using a stream (works for PDF/DOCX/images)
//     const result = await new Promise((resolve, reject) => {
//       const stream = cloudinary.uploader.upload_stream(
//         {
//           folder: "research-papers",
//           resource_type: "auto", // allows PDF, DOCX, images, etc.
//         },
//         (error, result) => {
//           if (error) reject(error);
//           else resolve(result);
//         }
//       );
//       stream.end(fileBuffer); // send the file buffer
//     });

//     // Save metadata to MongoDB
//     const paper = new Paper({
//       title: req.file.originalname,
//       originalName: req.file.originalname,
//       cloudinaryUrl: result.secure_url,
//       size: req.file.size,
//     });

//     await paper.save();

//     res.json({ message: "File uploaded successfully", paper });
//   } catch (err) {
//     console.error(err);
//     res.status(500).json({ error: "File upload failed", details: err.message });
//   }
// });

// module.exports = router;



// const express = require("express");
// const multer = require("multer");
// const { v2: cloudinary } = require("cloudinary");
// const streamifier = require("streamifier");
// const Paper = require("../models/paperModel");

// const router = express.Router();
// const storage = multer.memoryStorage();
// const upload = multer({ storage });

// cloudinary.config({
//   cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
//   api_key: process.env.CLOUDINARY_API_KEY,
//   api_secret: process.env.CLOUDINARY_API_SECRET,
// });

// router.post("/upload", upload.single("file"), async (req, res) => {
//   try {
//     if (!req.file) return res.status(400).json({ error: "No file uploaded" });

//     const fileBuffer = req.file.buffer;

//     const result = await new Promise((resolve, reject) => {
//       const stream = cloudinary.uploader.upload_stream(
//         { folder: "research-papers", resource_type: "auto" },
//         (error, result) => {
//           if (error) reject(error);
//           else resolve(result);
//         }
//       );
//       streamifier.createReadStream(fileBuffer).pipe(stream);
//     });

//     const paper = new Paper({
//       title: req.file.originalname,
//       originalName: req.file.originalname,
//       cloudinaryUrl: result.secure_url,
//       size: req.file.size,
//     });

//     await paper.save();

//     res.json({ message: "File uploaded successfully", paper });
//   } catch (err) {
//     console.error(err);
//     res.status(500).json({ error: "File upload failed", details: err.message });
//   }
// });

// module.exports = router;


const express = require("express");
const multer = require("multer");
const { v2: cloudinary } = require("cloudinary");
const streamifier = require("streamifier");
const Paper = require("../models/paperModel");

const router = express.Router();
const storage = multer.memoryStorage();
const upload = multer({ storage });

// Cloudinary config
cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});
console.log({
  CLOUDINARY_CLOUD_NAME: process.env.CLOUDINARY_CLOUD_NAME,
  CLOUDINARY_API_KEY: process.env.CLOUDINARY_API_KEY,
  CLOUDINARY_API_SECRET: process.env.CLOUDINARY_API_SECRET,
});

// POST /api/papers/upload
router.post("/upload", upload.single("file"), async (req, res) => {
  try {
    console.log("=== Upload request received ===");

    if (!req.file) {
      console.log("❌ No file uploaded");
      return res.status(400).json({ error: "No file uploaded" });
    }

    console.log("File info:", {
      originalname: req.file.originalname,
      mimetype: req.file.mimetype,
      size: req.file.size,
    });

    const fileBuffer = req.file.buffer;

    console.log("Uploading to Cloudinary...");

    const result = await new Promise((resolve, reject) => {
      const stream = cloudinary.uploader.upload_stream(
        { folder: "research-papers", resource_type: "auto" },
        (error, result) => {
          if (error) {
            console.error("❌ Cloudinary error:", error);
            reject(error);
          } else {
            console.log("✅ Cloudinary upload success:", result.secure_url);
            resolve(result);
          }
        }
      );

      // Convert buffer to stream and pipe
      streamifier.createReadStream(fileBuffer).pipe(stream);
    });

    console.log("Saving metadata to MongoDB...");
    const paper = new Paper({
      title: req.file.originalname,
      originalName: req.file.originalname,
      cloudinaryUrl: result.secure_url,
      size: req.file.size,
    });

    await paper.save();
    console.log("✅ Metadata saved:", paper._id);

    res.json({ message: "File uploaded successfully", paper });
  } catch (err) {
    console.error("❌ Upload route failed:", err);
    res.status(500).json({ error: "File upload failed", details: err.message });
  }
});

module.exports = router;

