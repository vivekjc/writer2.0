import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  LinearProgress,
  List,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Snackbar,
  Alert,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import axios from 'axios';
import BookActions from './BookActions';
import CostTracker from './CostTracker';

interface BookGeneratorProps {
  chapterBreakdown: any[];
}

interface GeneratedChapter {
  title: string;
  content: string;
  status: 'pending' | 'generating' | 'completed' | 'error';
  error?: string;
}

const BookGenerator: React.FC<BookGeneratorProps> = ({ chapterBreakdown }) => {
  const [generatedChapters, setGeneratedChapters] = useState<GeneratedChapter[]>(
    chapterBreakdown.map(chapter => ({
      title: chapter.title,
      content: '',
      status: 'pending'
    }))
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(-1);
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success'
  });
  const [bookFilename, setBookFilename] = useState<string | null>(null);
  const [currentDate] = useState<string>(new Date().toISOString().split('T')[0].replace(/-/g, ''));

  const generateChapter = async (chapter: any, index: number) => {
    setGeneratedChapters(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], status: 'generating' };
      return updated;
    });

    try {
      const WORDS_PER_CHUNK = 750;
      const numChunks = Math.ceil(chapter.wordCount / WORDS_PER_CHUNK);
      const wordsPerChunk = Math.ceil(chapter.wordCount / numChunks);
      
      console.log(`Breaking chapter ${index + 1} into ${numChunks} chunks of ~${wordsPerChunk} words each`);
      
      let fullContent = '';
      
      // Generate each chunk
      for (let chunkIndex = 0; chunkIndex < numChunks; chunkIndex++) {
        const startSection = Math.floor((chunkIndex * chapter.sections.length) / numChunks);
        const endSection = Math.floor(((chunkIndex + 1) * chapter.sections.length) / numChunks);
        const chunkSections = chapter.sections.slice(startSection, endSection + 1);
        
        const prompt = `${chapter.title} - Part ${chunkIndex + 1} of ${numChunks}

This is part ${chunkIndex + 1} of ${numChunks} for this chapter. 
${chunkIndex === 0 ? 'Start with a proper introduction.' : 'Continue from the previous part.'}
${chunkIndex === numChunks - 1 ? 'End with a proper conclusion.' : 'Leave the section open for continuation.'}

Sections to cover in this part:
${chunkSections.join('\n')}

Generate approximately ${wordsPerChunk} words.
${chunkIndex === numChunks - 1 ? 'Include references section at the end.' : ''}`;

        const response = await axios.post('http://localhost:8000/api/generate-chapter', {
          chapter_id: index + 1,
          content: prompt
        });

        const newContent = fullContent + (chunkIndex > 0 ? '\n\n' : '') + response.data.content;
        fullContent = newContent;
        
        // Update progress
        setGeneratedChapters(prev => {
          const updated = [...prev];
          updated[index] = {
            ...updated[index],
            content: newContent,
            status: 'generating'
          };
          return updated;
        });
      }

      // Final update with complete content
      setGeneratedChapters(prev => {
        const updated = [...prev];
        updated[index] = {
          ...updated[index],
          content: fullContent,
          status: 'completed'
        };
        return updated;
      });
    } catch (error) {
      console.error(`Error generating chapter ${index + 1}:`, error);
      setGeneratedChapters(prev => {
        const updated = [...prev];
        updated[index] = {
          ...updated[index],
          status: 'error',
          error: 'Failed to generate chapter'
        };
        return updated;
      });
    }
  };

  const handleGenerateBook = async () => {
    setIsGenerating(true);
    setCurrentChapterIndex(0);

    for (let i = 0; i < chapterBreakdown.length; i++) {
      setCurrentChapterIndex(i);
      await generateChapter(chapterBreakdown[i], i);
    }

    setIsGenerating(false);
    setCurrentChapterIndex(-1);

    // Save the completed book
    try {
      const completedChapters = generatedChapters.map((chapter, index) => ({
        title: chapter.title,
        content: chapter.content,
        wordCount: chapterBreakdown[index].wordCount,
        sections: chapterBreakdown[index].sections
      }));

      await axios.post('http://localhost:8000/api/save-book', {
        chapters: completedChapters,
        outline_filename: localStorage.getItem('lastOutlineFilename') || 'unknown'
      });

      setNotification({
        open: true,
        message: 'Book has been saved successfully!',
        severity: 'success'
      });
      setBookFilename('software-engineers-handbook.txt');
    } catch (error) {
      setNotification({
        open: true,
        message: 'Failed to save the book. Please try again.',
        severity: 'error'
      });
    }
  };

  const downloadBook = () => {
    const content = generatedChapters
      .map(chapter => `${chapter.title}\n\n${chapter.content}\n\n`)
      .join('\n---\n\n');
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'software-engineers-handbook.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const getProgress = () => {
    const completed = generatedChapters.filter(
      chapter => chapter.status === 'completed'
    ).length;
    return (completed / generatedChapters.length) * 100;
  };

  const handleCloseNotification = () => {
    setNotification(prev => ({ ...prev, open: false }));
  };

  return (
    <Box sx={{ mt: 2, pb: 10 }}>
      <Typography variant="h6" gutterBottom>
        Generate Book Content
      </Typography>

      {!isGenerating && currentChapterIndex === -1 && (
        <Button
          variant="contained"
          color="primary"
          onClick={handleGenerateBook}
          sx={{ mb: 3 }}
          disabled={chapterBreakdown.length === 0}
        >
          Start Generating Book
        </Button>
      )}

      {isGenerating && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" gutterBottom>
            Generating Chapter {currentChapterIndex + 1} of {chapterBreakdown.length}
          </Typography>
          <LinearProgress variant="determinate" value={getProgress()} />
        </Box>
      )}

      <List>
        {generatedChapters.map((chapter, index) => (
          <Accordion key={index} sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <Typography sx={{ flexGrow: 1 }}>{chapter.title}</Typography>
                {chapter.status === 'generating' && <CircularProgress size={20} sx={{ ml: 2 }} />}
                {chapter.status === 'completed' && (
                  <Typography variant="body2" color="success.main" sx={{ ml: 2 }}>
                    Completed
                  </Typography>
                )}
                {chapter.status === 'error' && (
                  <Typography variant="body2" color="error" sx={{ ml: 2 }}>
                    Error
                  </Typography>
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Typography
                variant="body2"
                component="pre"
                sx={{ whiteSpace: 'pre-wrap' }}
              >
                {chapter.content || 'Content not generated yet'}
              </Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </List>

      {generatedChapters.some(chapter => chapter.status === 'completed') && (
        <Button
          variant="contained"
          color="secondary"
          onClick={downloadBook}
          sx={{ mt: 2 }}
        >
          Download Book
        </Button>
      )}

      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={handleCloseNotification}
      >
        <Alert
          onClose={handleCloseNotification}
          severity={notification.severity}
          sx={{ width: '100%' }}
        >
          {notification.message}
        </Alert>
      </Snackbar>

      {bookFilename && <BookActions bookFilename={bookFilename} />}

      <CostTracker
        chapterCount={chapterBreakdown.length}
        completedChapters={generatedChapters.filter(ch => ch.status === 'completed').length}
        currentDate={currentDate}
      />
    </Box>
  );
};

export default BookGenerator; 